/*
  ===========================================================================
  SMART LAB — ESP32-CAM  STAGE 3:  QR + FACE, NO MODE SWITCHING
  ===========================================================================
  Board: AI Thinker ESP32-CAM (OV2640)

  WHAT THIS DOES
  Captures a JPEG a few times a second and POSTs it to the laptop's /analyze
  endpoint, which returns BOTH a QR payload and a face identity from the same
  frame. The most recent result is cached and served to the Master ESP32 on
  GET /status.

  WHY THERE IS NO MODE SWITCHING
  The obvious design was to switch the camera between a QR mode and a face
  mode on command. That means tearing down and rebuilding the camera driver
  at runtime - fragile, and there is only one physical camera to fight over.
  Sending one frame and letting the laptop do both jobs removes the problem
  completely: one camera config, one code path, nothing to switch. It also
  decodes QR more reliably, because OpenCV on a laptop beats quirc on an
  ESP32. The ESP32QRCodeReader library is no longer needed at all.

  ---------------------------------------------------------------------------
  NO EXTRA LIBRARIES NEEDED
  WiFi.h, HTTPClient.h and esp_camera.h all ship with the ESP32 board package.

  ---------------------------------------------------------------------------
  ENDPOINTS THIS BOARD SERVES (the Master ESP32 polls these)

    GET /status
        {"qr":"USER1","qr_age_ms":420,"face":"USER2","face_age_ms":1300,
         "distance":41.2,"online":true}
        age_ms = how long ago that result was seen. -1 means never.
        The master uses the age to ignore stale results - critical, or a QR
        scanned a minute ago could unlock the door for the next person.

    GET /enroll?name=USER1    capture one face sample (enrollment)
    GET /snapshot             plain JPEG, for checking framing
    GET /                     small status page

  ---------------------------------------------------------------------------
  SETUP
    1. Laptop:  python face_server.py
    2. Set RECOGNITION_SERVER_IP below to the laptop's IP
    3. Flash, note the camera's IP from Serial - the Master needs it
  ===========================================================================
*/

#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_http_server.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// WIFI_SSID and WIFI_PASS live in secrets.h, which is gitignored.
// Copy secrets.example.h to secrets.h and fill in your network.
#include "secrets.h"

// ===========================================================================
// >>>>>>>>>>>>>>>>>>>>>>>>>>> EDIT THESE <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
// ===========================================================================

const char *SERVER_IP   = "192.168.1.8";   // laptop running face_server.py
const int   SERVER_PORT = 5000;

// How often to send a frame. Faster feels more responsive at the door but
// loads the WiFi and the laptop; 1200ms is a reasonable balance.
constexpr uint32_t ANALYZE_INTERVAL_MS = 150;

// JPEG quality, 0-63, LOWER = better quality and a BIGGER file. Every frame
// is uploaded over WiFi, so file size is frame rate: at a weak signal the
// upload, not the laptop, is what limits speed. 12 made ~20 KB frames;
// 18 roughly halves that, and on simulated door frames the QR still decoded
// every time. If face distances rise noticeably, go back towards 14.
constexpr int JPEG_QUALITY = 18;

// How many frames may be in flight to the laptop at once. The link to the
// laptop is LATENCY-bound, not bandwidth-bound: halving the JPEG size only
// cut each round trip from ~620 to ~450 ms. With one frame at a time the
// camera sits idle for that whole round trip; with 2, the next frame is
// already travelling while the previous one is analysed, roughly doubling
// frames/s at the same image quality.
// Set to 1 for the exact previous behaviour (one frame at a time).
constexpr int ANALYZE_WORKERS = 2;

// Print a [PERF] line this often: frames/s actually sent and where the time
// goes (capture vs upload+reply). Set to 0 to silence it.
constexpr uint32_t PERF_EVERY_MS = 10000;

// ===========================================================================
// AI-THINKER ESP32-CAM PIN MAP
// ===========================================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

httpd_handle_t server = NULL;

// ---------------------------------------------------------------------------
// Cached results. The master polls these rather than waiting on the laptop,
// so a slow recognition never stalls the door.
// ---------------------------------------------------------------------------
String   lastQr        = "";
uint32_t lastQrMs      = 0;
bool     everQr        = false;

String   lastFace      = "";
uint32_t lastFaceMs    = 0;
bool     everFace      = false;
float    lastDistance  = 0;

volatile bool analyzeBusy = false;   // set by /enroll to pause analysis

// Guards everything above and below that the analyze workers, the HTTP
// server's /status handler and /enroll share. Held only while touching that
// state - never across a camera capture or a network request.
SemaphoreHandle_t stateLock = NULL;
#define LOCK()   xSemaphoreTake(stateLock, portMAX_DELAY)
#define UNLOCK() xSemaphoreGive(stateLock)

// One per in-flight frame: each keeps its own TCP connection to the laptop.
struct AnalyzeWorker {
  WiFiClient client;
  HTTPClient http;
  uint32_t   lastStartMs = 0;
};
AnalyzeWorker workers[ANALYZE_WORKERS];

// Failure handling for the laptop link. After a failed frame the next one is
// delayed a little more each time (up to ANALYZE_BACKOFF_MAX_MS), so a laptop
// that is busy or briefly unreachable is not hammered 7 times a second, and
// the log shows one line per outage instead of hundreds.
constexpr uint32_t ANALYZE_BACKOFF_STEP_MS = 150;
constexpr uint32_t ANALYZE_BACKOFF_MAX_MS  = 1500;
uint32_t analyzeFails   = 0;
uint32_t analyzeDelayMs = 0;     // extra delay before the next frame
uint32_t lastFailLogMs  = 0;

// [PERF] accumulators
uint32_t perfStartMs = 0, perfFrames = 0, perfFails = 0;
uint32_t perfCaptureMs = 0, perfPostMs = 0, perfBytes = 0;

// Timing of the PREVIOUS frame, sent as headers with the next one so the
// face server can print the camera's side of the story in its [stats] line
// (one window to read instead of two).
uint32_t prevCaptureMs = 0, prevPostMs = 0, totalFails = 0;

void perfReport() {
  if (PERF_EVERY_MS == 0) return;
  uint32_t now = millis();
  if (perfStartMs == 0) { perfStartMs = now; return; }
  uint32_t elapsed = now - perfStartMs;
  if (elapsed < PERF_EVERY_MS) return;
  uint32_t n = perfFrames + perfFails;
  if (n > 0) {
    Serial.printf("[PERF] %.1f frames/s ok, %u failed | capture %u ms, upload+reply %u ms,"
                  " %u KB/frame | WiFi %d dBm\n",
                  perfFrames * 1000.0f / elapsed, (unsigned)perfFails,
                  (unsigned)(perfCaptureMs / n), (unsigned)(perfPostMs / n),
                  (unsigned)(perfBytes / n / 1024), WiFi.RSSI());
  }
  perfStartMs = now;
  perfFrames = perfFails = perfCaptureMs = perfPostMs = perfBytes = 0;
}

// ===========================================================================
// Camera capture with retry - the ESP32-CAM often fails the first capture
// after boot, and a brief power dip can fail one mid-run.
// ===========================================================================
camera_fb_t *captureWithRetry() {
  for (int attempt = 1; attempt <= 3; attempt++) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (fb) return fb;
    delay(100);
  }
  Serial.printf("[CAM][FAIL] no frame. psram=%s free_psram=%u free_heap=%u\n",
                psramFound() ? "yes" : "NO",
                (unsigned)ESP.getFreePsram(), (unsigned)ESP.getFreeHeap());
  return NULL;
}

// ===========================================================================
// Tiny JSON string extractor. A full JSON parser is overkill for three fixed
// fields, and avoiding ArduinoJson keeps this sketch dependency-free.
// Returns "" when the key is null or absent.
// ===========================================================================
String jsonString(const String &src, const String &key) {
  int k = src.indexOf("\"" + key + "\"");
  if (k < 0) return "";
  int colon = src.indexOf(':', k);
  if (colon < 0) return "";
  int q1 = src.indexOf('"', colon);
  // If the value is null (no quote before the next comma/brace) there is no
  // string to return.
  int comma = src.indexOf(',', colon);
  int brace = src.indexOf('}', colon);
  int end   = (comma >= 0 && comma < brace) ? comma : brace;
  if (q1 < 0 || q1 > end) return "";
  int q2 = src.indexOf('"', q1 + 1);
  if (q2 < 0) return "";
  return src.substring(q1 + 1, q2);
}

float jsonNumber(const String &src, const String &key) {
  int k = src.indexOf("\"" + key + "\"");
  if (k < 0) return 0;
  int colon = src.indexOf(':', k);
  if (colon < 0) return 0;
  return src.substring(colon + 1).toFloat();
}

// ===========================================================================
// Send one frame to the laptop and cache whatever comes back.
// ===========================================================================
void analyzeFrame(AnalyzeWorker &w) {
  if (WiFi.status() != WL_CONNECTED) return;

  uint32_t tCap = millis();
  camera_fb_t *fb = captureWithRetry();
  if (!fb) return;
  uint32_t capMs = millis() - tCap;

  uint32_t hdrCapMs, hdrPostMs, hdrFails;
  LOCK();
  prevCaptureMs  = capMs;
  perfCaptureMs += capMs;
  perfBytes     += fb->len;
  hdrCapMs = prevCaptureMs;  hdrPostMs = prevPostMs;  hdrFails = totalFails;
  UNLOCK();

  // Per-worker client, so the TCP connection survives between frames. At a
  // weak signal the handshake alone can cost more than the image transfer.
  WiFiClient &client = w.client;
  HTTPClient &http   = w.http;
  String url = String("http://") + SERVER_IP + ":" + SERVER_PORT + "/analyze";
  http.begin(client, url);
  http.setReuse(true);
  // Send every TCP segment immediately. By default lwIP holds back the last,
  // partly-filled segment of each upload until the previous one is ACKed,
  // and Windows delays ACKs by up to 200 ms - a stall on EVERY frame.
  client.setNoDelay(true);
  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Cam-Rssi", String(WiFi.RSSI()));
  http.addHeader("X-Cam-Capture-Ms", String(hdrCapMs));
  http.addHeader("X-Cam-Post-Ms", String(hdrPostMs));
  http.addHeader("X-Cam-Fails", String(hdrFails));
  http.setConnectTimeout(1500);
  http.setTimeout(2000);

  uint32_t tPost = millis();
  int code = http.POST(fb->buf, fb->len);
  String body;
  if (code == 200) {
    body = http.getString();
  } else {
    // Throw the connection away: after a timeout or reset, reusing it makes
    // the NEXT frame fail too, which is how one hiccup became a long run of
    // -1 / -11 errors.
    client.stop();
  }
  http.end();
  uint32_t postMs = millis() - tPost;
  esp_camera_fb_return(fb);

  // Everything below touches shared state.
  LOCK();
  prevPostMs  = postMs;
  perfPostMs += postMs;

  if (code == 200) {
    perfFrames++;
    if (analyzeFails > 0) {
      Serial.printf("[ANALYZE] laptop reachable again (after %u failed frames)\n",
                    (unsigned)analyzeFails);
    }
    analyzeFails   = 0;
    analyzeDelayMs = 0;

    String qr = jsonString(body, "qr");
    if (qr.length() > 0) {
      // Print a QR when it first appears (or reappears after 2 s), not on
      // every frame it stays in view - the cache is refreshed either way.
      if (qr != lastQr || millis() - lastQrMs > 2000) {
        Serial.printf("[QR]   %s\n", qr.c_str());
      }
      lastQr   = qr;
      lastQrMs = millis();
      everQr   = true;
    }

    String face = jsonString(body, "face");
    if (face.length() > 0) {
      lastFace     = face;
      lastFaceMs   = millis();
      everFace     = true;
      lastDistance = jsonNumber(body, "distance");
      Serial.printf("[FACE] %s  (distance %.1f)\n", face.c_str(), lastDistance);
    }
  } else {
    perfFails++;
    totalFails++;
    analyzeFails++;
    analyzeDelayMs = std::min<uint32_t>(analyzeFails * ANALYZE_BACKOFF_STEP_MS,
                                   ANALYZE_BACKOFF_MAX_MS);
    if (analyzeFails == 1 || millis() - lastFailLogMs > 5000) {
      lastFailLogMs = millis();
      const char *why =
        code == HTTPC_ERROR_CONNECTION_REFUSED ? "cannot connect - is face_server.py running, firewall open?" :
        code == HTTPC_ERROR_READ_TIMEOUT       ? "laptop too slow to answer (busy, or its console window is paused?)" :
        code == HTTPC_ERROR_CONNECTION_LOST    ? "connection dropped" :
        code == HTTPC_ERROR_SEND_PAYLOAD_FAILED ? "image upload failed (weak WiFi?)" :
                                                  "request failed";
      Serial.printf("[ANALYZE] HTTP %d - %s  [%s:%d, %u fails, WiFi %d dBm]\n",
                    code, why, SERVER_IP, SERVER_PORT,
                    (unsigned)analyzeFails, WiFi.RSSI());
    }
  }
  perfReport();
  UNLOCK();
}

// Each worker sends frames back to back (at most one per ANALYZE_INTERVAL_MS,
// plus the shared back-off after failures). Running ANALYZE_WORKERS of them
// keeps that many frames in flight.
void analyzeTask(void *arg) {
  AnalyzeWorker &w = *static_cast<AnalyzeWorker *>(arg);
  // Staggered start so the workers settle into alternating frames.
  int index = &w - workers;
  vTaskDelay(pdMS_TO_TICKS(index * ANALYZE_INTERVAL_MS / ANALYZE_WORKERS));
  for (;;) {
    LOCK();
    uint32_t gap = ANALYZE_INTERVAL_MS + analyzeDelayMs;
    UNLOCK();
    if (!analyzeBusy && millis() - w.lastStartMs > gap) {
      w.lastStartMs = millis();
      analyzeFrame(w);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

// ===========================================================================
// GET /status  - what the Master ESP32 polls
// ===========================================================================
static esp_err_t status_handler(httpd_req_t *req) {
  char buf[256];
  LOCK();
  long qrAge   = everQr   ? (long)(millis() - lastQrMs)   : -1;
  long faceAge = everFace ? (long)(millis() - lastFaceMs) : -1;

  int len = snprintf(buf, sizeof(buf),
    "{\"qr\":%s%s%s,\"qr_age_ms\":%ld,"
    "\"face\":%s%s%s,\"face_age_ms\":%ld,"
    "\"distance\":%.1f,\"online\":true}",
    everQr ? "\"" : "", everQr ? lastQr.c_str() : "null", everQr ? "\"" : "",
    qrAge,
    everFace ? "\"" : "", everFace ? lastFace.c_str() : "null", everFace ? "\"" : "",
    faceAge,
    lastDistance);
  UNLOCK();

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, buf, len);
}

// ===========================================================================
// GET /enroll?name=USER1  - forward one frame to the laptop as training data
// ===========================================================================
static esp_err_t enroll_handler(httpd_req_t *req) {
  char query[64], name[32] = "";
  if (httpd_req_get_url_query_str(req, query, sizeof(query)) == ESP_OK) {
    httpd_query_key_value(query, "name", name, sizeof(name));
  }
  if (strlen(name) == 0) {
    const char *msg = "{\"error\":\"use /enroll?name=USER1\"}";
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, msg, strlen(msg));
  }

  analyzeBusy = true;                 // pause the analyze loop for this frame
  String reply = "{\"error\":\"capture failed\"}";

  camera_fb_t *fb = captureWithRetry();
  if (fb) {
    HTTPClient http;
    String url = String("http://") + SERVER_IP + ":" + SERVER_PORT +
                 "/enroll?name=" + String(name);
    http.begin(url);
    http.addHeader("Content-Type", "image/jpeg");
    http.setTimeout(6000);
    int code = http.POST(fb->buf, fb->len);
    reply = (code == 200) ? http.getString()
                          : String("{\"error\":\"HTTP ") + code + "\"}";
    http.end();
    esp_camera_fb_return(fb);
  }

  analyzeBusy   = false;
  Serial.printf("[ENROLL] %s -> %s\n", name, reply.c_str());

  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_send(req, reply.c_str(), reply.length());
}

static esp_err_t snapshot_handler(httpd_req_t *req) {
  camera_fb_t *fb = captureWithRetry();
  if (!fb) { httpd_resp_send_500(req); return ESP_FAIL; }
  httpd_resp_set_type(req, "image/jpeg");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

static esp_err_t index_handler(httpd_req_t *req) {
  LOCK();
  String qrNow   = everQr   ? lastQr   : String("none");
  String faceNow = everFace ? lastFace : String("none");
  UNLOCK();
  String html =
    "<html><head><meta http-equiv='refresh' content='2'></head>"
    "<body style='font-family:sans-serif;background:#111;color:#eee;padding:20px'>"
    "<h2>Smart Lab Camera - Stage 3</h2>"
    "<p>Last QR   : <b>" + qrNow   + "</b></p>"
    "<p>Last face : <b>" + faceNow + "</b></p>"
    "<hr>"
    "<p><a style='color:#6cf' href='/enroll?name=USER1'>enroll USER1</a> | "
    "<a style='color:#6cf' href='/enroll?name=USER2'>enroll USER2</a></p>"
    "<p><a style='color:#6cf' href='/snapshot'>snapshot</a> | "
    "<a style='color:#6cf' href='/status'>status JSON</a></p>"
    "</body></html>";
  httpd_resp_set_type(req, "text/html");
  return httpd_resp_send(req, html.c_str(), html.length());
}

void startServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port      = 80;
  config.stack_size       = 8192;
  config.max_open_sockets = 4;

  static httpd_uri_t index_uri    = { "/",         HTTP_GET, index_handler,    NULL };
  static httpd_uri_t status_uri   = { "/status",   HTTP_GET, status_handler,   NULL };
  static httpd_uri_t enroll_uri   = { "/enroll",   HTTP_GET, enroll_handler,   NULL };
  static httpd_uri_t snapshot_uri = { "/snapshot", HTTP_GET, snapshot_handler, NULL };

  if (httpd_start(&server, &config) == ESP_OK) {
    httpd_register_uri_handler(server, &index_uri);
    httpd_register_uri_handler(server, &status_uri);
    httpd_register_uri_handler(server, &enroll_uri);
    httpd_register_uri_handler(server, &snapshot_uri);
    Serial.println("[INIT] HTTP server started on port 80.");
  }
}

// ===========================================================================
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);   // stop spurious brownout resets
  stateLock = xSemaphoreCreateMutex();

  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=================================================");
  Serial.println(" SMART LAB - ESP32-CAM  STAGE 3: QR + FACE");
  Serial.println("=================================================");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk  = XCLK_GPIO_NUM;   config.pin_pclk  = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;  config.pin_href  = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;   config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;

  // ONE configuration serving both jobs. VGA + good quality: faces need the
  // detail, and QR codes decode more reliably at higher resolution too.
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_VGA;    // 640x480
  config.jpeg_quality = JPEG_QUALITY;
  config.grab_mode    = CAMERA_GRAB_LATEST;

  if (psramFound()) {
    config.fb_count    = ANALYZE_WORKERS + 1;   // one per in-flight frame + one filling
    config.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    config.frame_size  = FRAMESIZE_QVGA;
    config.fb_count    = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    Serial.println("[INIT] No PSRAM - falling back to QVGA.");
  }

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("[INIT][FAIL] Camera init failed.");
    return;
  }

  camera_fb_t *test = captureWithRetry();
  if (test) {
    Serial.printf("[INIT] Camera OK: %u bytes, %ux%u\n",
                  (unsigned)test->len, test->width, test->height);
    esp_camera_fb_return(test);
  } else {
    Serial.println("[INIT][FAIL] Camera cannot capture - check power.");
  }

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WIFI] Connecting");
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(300); Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WIFI][FAIL] Not connected.");
    return;
  }
  WiFi.setSleep(false);

  Serial.print("[WIFI] Camera IP: ");
  Serial.println(WiFi.localIP());
  Serial.printf("[WIFI] Signal: %d dBm\n", WiFi.RSSI());

  startServer();

  Serial.println();
  Serial.println("=================================================");
  Serial.println("                    READY");
  Serial.println("=================================================");
  Serial.print  ("PUT THIS IP IN THE MASTER SKETCH: ");
  Serial.println(WiFi.localIP());
  Serial.printf ("Analyzing via http://%s:%d/analyze, %d frame(s) in flight\n",
                 SERVER_IP, SERVER_PORT, ANALYZE_WORKERS);

  for (int i = 0; i < ANALYZE_WORKERS; i++) {
    char name[16];
    snprintf(name, sizeof(name), "analyze%d", i);
    xTaskCreatePinnedToCore(analyzeTask, name, 8192, &workers[i], 1, NULL, 1);
  }
  Serial.println("-------------------------------------------------");
}

// ===========================================================================
void loop() {
  // All work happens in the analyze tasks and the HTTP server.
  vTaskDelay(pdMS_TO_TICKS(1000));
}
