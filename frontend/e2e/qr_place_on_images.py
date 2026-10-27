import cv2, numpy as np, json, os, sys
from PIL import Image, ImageDraw, ImageFilter
D = sys.argv[1]; SC = 6
M = json.load(open(D + '/../qrart/matrices.json'))
MAP = {'01_admin_laptop': ('admin-laptop', 'SLAB:D:PC_ADMIN_LAPTOP'), '02_consumables_bin': ('consumables-bin', 'SLAB:D:BIN_NODE_1'),
       '03_master_door_controller': ('door-master', 'SLAB:D:MASTER_LAB01'), '04_entry_camera': ('entry-camera', 'SLAB:D:CAM_LAB01'),
       '05_face_recognition_server': ('face-server', 'SLAB:D:FACESRV_01'), '06_fanuc_robot_arm': ('fanuc-robot', 'SLAB:D:FANUC_01'),
       '07_reusable_items_bin': ('reusable-bin', 'SLAB:D:REUSE_BIN_1'), '08_security_camera': ('security-camera', 'SLAB:D:SECCAM_LAB01'),
       '09_lab_pc_01': ('student-pc', 'SLAB:D:PC_01'), '10_ur5e_robot_arm': ('ur5e-robot', 'SLAB:D:UR5E_01')}
os.makedirs(D + '/png', exist_ok=True)
man = []
for stem, (slug, code) in MAP.items():
    a = cv2.imread(f'{D}/src/{stem}.png'); h, w = a.shape[:2]
    if stem.startswith('03_'):
        box = (72, 298, 96, 96)                       # sticker on the door leaf, below the handle (owner image has no panel there)
    else:
        g = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        m = ((g >= 248) & (a.max(2).astype(int) - a.min(2) <= 6)).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        c = [st[i] for i in range(1, n) if st[i][0] > 2 and st[i][1] > 2 and st[i][0] + st[i][2] < w - 3 and st[i][1] + st[i][3] < h - 3]
        x, y, bw, bh, _ = max(c, key=lambda s: s[4]); box = (int(x), int(y), int(bw), int(bh))
    img = Image.open(f'{D}/src/{stem}.png').convert('RGB')
    img = img.resize((w * SC, h * SC), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
    d = ImageDraw.Draw(img)
    x, y, bw, bh = [v * SC for v in box]
    if stem.startswith('03_'):                         # the sticker itself: soft shadow, white, thin grey edge
        sh = Image.new('L', img.size, 0); ImageDraw.Draw(sh).rounded_rectangle((x + 8, y + 14, x + bw + 8, y + bh + 14), 40, fill=120)
        img.paste((10, 40, 40), mask=sh.filter(ImageFilter.GaussianBlur(14)))
        d.rounded_rectangle((x, y, x + bw, y + bh), 40, fill='white', outline=(190, 200, 205), width=6)
    mat = M[code]; n = len(mat)
    inner = min(bw, bh) * 0.92
    k = int(inner // (n + 6))                          # 3-module quiet zone inside the white panel (the panel adds more)
    size = k * n; ox = int(x + (bw - size) / 2); oy = int(y + (bh - size) / 2)
    d.rectangle((ox - 3 * k, oy - 3 * k, ox + size + 3 * k - 1, oy + size + 3 * k - 1), fill='white')
    for r, row in enumerate(mat):
        for cc, v in enumerate(row):
            if v == '1': d.rectangle((ox + cc * k, oy + r * k, ox + cc * k + k - 1, oy + r * k + k - 1), fill=(11, 19, 36))
    img.save(f'{D}/png/{slug}.png', dpi=(300, 300), optimize=True)
    man.append({'file': f'{slug}.png', 'payload': code, 'source_image': f'{stem}.png', 'module_px': k, 'size': list(img.size)})
    print(slug, code, 'module', k, 'px', img.size)
json.dump(man, open(D + '/manifest.json', 'w'), indent=1)
