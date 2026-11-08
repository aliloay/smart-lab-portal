# Smart Lab Visual AI - working plan (owner's revised plan, 2026-10-28)

Status labels: **done** = running and verified, **next** = ready to start once data exists, **later** = after round one.

## Where we are (2026-10-28)
- **done** QR marker identity (exact asset ID from the registry); jsQR on the phone.
- **done** People boxes (camera-service YOLO26s, COCO person + monitor/laptop/keyboard) and face naming on a clear match.
- **done** "Which box is this?" appearance hint (ORB + RANSAC against the owner's photos of the reusable bin, 27 photos):
  leave-one-out 22/27 correct, 0 wrong; runs every 3 s while no marker is in view; dashed frame around the matched
  points; message fades after 5 s. Hint only - live data needs the marker. Close range only (the bin must fill a good
  part of the frame); 7/7 owner wide photos = "not recognised"; 4/4 non-bin pictures = "not recognised".
- **tried, not deployed** YOLO11n trained on 27 bin close-ups only: 7/7 wide photos found but also 3/4 pictures with no
  bin at 0.8-0.98 - no negatives in training. Kept off the portal (tools/vision_train/).

## Round one - 12 classes (frozen names)
| ID | Class | Box rule |
|---|---|---|
| 0 | person | whole visible body |
| 1 | ur5e_robot | the arm as a whole (base to tool), not the stand |
| 2 | fanuc_robot | the arm as a whole |
| 3 | robot_controller | the controller cabinet / box |
| 4 | lab_computer_station | ONE box around monitor + PC unit + keyboard together |
| 5 | master_door_unit | the printed master door enclosure (front panel visible) |
| 6 | environment_node | the printed environment enclosure |
| 7 | consumables_node | the consumables scale console |
| 8 | reusable_bin_node | the bin AND its control box together (as in make_dataset.py) |
| 9 | plc_cabinet | the PLC trainer / cabinet front |
| 10 | security_camera | the camera body (not the bracket) |
| 11 | networking_device | the router / switch body |

## Data to collect (owner, phone camera, NO people except for class 0 with consent)
Per class 100-300 images (target, not a guarantee), from **separate sessions** so near-identical frames do not leak
across train/val/test:
1. Distances 0.5 m / 1-2 m / 3-5 m (across the room), 5+ angles, lab lighting + daylight, partly hidden.
2. **Negatives**: 150+ lab photos/video with NONE of the 12 classes (desks, floor, walls, other boxes, bags, cables).
3. Short slow videos are fine (frames are sampled ~2/s; one video = one session = one split).
4. Hard cases: the three printed nodes (5-8) next to each other - they look alike.

Split by session: 70 % train / 15 % val / 15 % test, manifest frozen before any model comparison.

## Training and comparison (next)
- YOLO11n and YOLO26n from pretrained weights, same frozen dataset, imgsz 640 (and 416), same epochs/augmentation.
- One run each; three seeds each if mAP50-95 is within ~1-2 points or they trade accuracy for speed.
- Report per class: precision, recall, mAP50, mAP50-95, confusion matrix (nodes 5-8 especially), misses by class,
  **false detections per minute on the negative video**, inference ms, end-to-end ms (capture -> visible label),
  capture -> speech start, sustained FPS, flicker / lost IDs. Median and p95; device, runtime, resolution recorded.
- Deployment benchmark on the real targets: iPhone Safari (ONNX Runtime Web, WASM/WebGPU) and the laptop camera
  service (ONNX DirectML). Core ML / native app only if the browser is too slow.

## Integration rules (later, after a model passes)
- Stable label only after 3 of the last 5 frames; per-class thresholds; box smoothing; hysteresis; uncertain on drop.
- Identity priority: valid registry marker -> exact asset; else class only ("a lab PC"); else "unidentified equipment".
  Never an asset number from appearance alone; marker/vision type mismatch flagged for review.
- Speech modes Scan / Speak once per stable track / Tell me more; live facts only from backend records.
- Privacy: "person detected" unless a consented, registered user is matched by the existing face rule; inference
  on-device or lab-local; vision never opens a door or moves a robot.

## Thesis comparison
Appearance-only vs marker-only vs hybrid on the same unseen sessions (marker visible / partly / absent, no-target
scenes); results table filled only with measured numbers, coverage reported next to accuracy.
