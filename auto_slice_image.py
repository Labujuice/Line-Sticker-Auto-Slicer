#!/usr/bin/env python3
import os
import sys
import argparse
import numpy as np
import cv2
from PIL import Image, ImageColor, ImageChops

def parse_size(size_str):
    """Parse size string in WIDTHxHEIGHT format."""
    if not size_str:
        return None
    try:
        parts = size_str.lower().split('x')
        if len(parts) != 2:
            raise ValueError()
        w, h = map(int, parts)
        if w <= 0 or h <= 0:
            raise ValueError()
        return w, h
    except ValueError:
        raise argparse.ArgumentTypeError("尺寸格式必須是 寬x高，例如: 240x240，且必須為正整數。")

def parse_color(color_str):
    """Parse color string, supporting 'transparent' and hex/names."""
    color_str = color_str.strip().lower()
    if color_str in ('transparent', 'none', 'clear'):
        return (0, 0, 0, 0)
    try:
        return ImageColor.getcolor(color_str, 'RGBA')
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"無法解析的顏色格式: '{color_str}'。支援 'transparent' 或標準顏色名稱 (如 white, black) 或十六進制 (如 #ffffff, #ff000080)"
        )

def get_interactive_input(prompt_text, default_val=None, validator=None):
    """Helper to get and validate input interactively."""
    while True:
        try:
            val = input(prompt_text).strip()
            if not val:
                if default_val is not None:
                    return default_val
                print("此欄位為必填，請輸入值。")
                continue
            
            if validator:
                return validator(val)
            return val
        except Exception as e:
            print(f"輸入錯誤: {e}，請重新輸入。")

def resize_image(img, target_size, mode, pad_color_rgba):
    """Resize image according to specified mode and target size."""
    target_w, target_h = target_size
    img_w, img_h = img.size

    if mode == 'stretch':
        return img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    aspect_target = target_w / target_h
    aspect_img = img_w / img_h
    
    if mode == 'fit':
        if aspect_img > aspect_target:
            new_w = target_w
            new_h = max(1, int(target_w / aspect_img))
        else:
            new_h = target_h
            new_w = max(1, int(target_h * aspect_img))
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
    elif mode == 'pad':
        if aspect_img > aspect_target:
            new_w = target_w
            new_h = max(1, int(target_w / aspect_img))
        else:
            new_h = target_h
            new_w = max(1, int(target_h * aspect_img))
            
        resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        if pad_color_rgba[3] < 255 or img.mode == 'RGBA':
            background = Image.new('RGBA', (target_w, target_h), pad_color_rgba)
        else:
            background = Image.new(img.mode, (target_w, target_h), pad_color_rgba[:3] if img.mode == 'RGB' else pad_color_rgba)
            
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        
        if resized_img.mode == 'RGBA':
            background.paste(resized_img, (offset_x, offset_y), resized_img)
        else:
            background.paste(resized_img, (offset_x, offset_y))
            
        return background
    
    return img

def merge_boxes(boxes, gap):
    """Merge bounding boxes that are close to each other (distance <= gap)."""
    merged = True
    while merged:
        merged = False
        new_boxes = []
        visited = set()
        for i in range(len(boxes)):
            if i in visited:
                continue
            x1_i, y1_i, x2_i, y2_i = boxes[i]
            
            for j in range(i + 1, len(boxes)):
                if j in visited:
                    continue
                x1_j, y1_j, x2_j, y2_j = boxes[j]
                
                # Check if boxes overlap when expanded by half the gap
                pad = gap / 2.0
                overlap_x = not (x2_i + pad < x1_j - pad or x2_j + pad < x1_i - pad)
                overlap_y = not (y2_i + pad < y1_j - pad or y2_j + pad < y1_i - pad)
                
                if overlap_x and overlap_y:
                    x1_i = min(x1_i, x1_j)
                    y1_i = min(y1_i, y1_j)
                    x2_i = max(x2_i, x2_j)
                    y2_i = max(y2_i, y2_j)
                    visited.add(j)
                    merged = True
                    
            new_boxes.append([x1_i, y1_i, x2_i, y2_i])
        boxes = new_boxes
    return boxes

def detect_objects(image_path, min_size=15, gap=30, debug_output=None):
    """
    Detect non-background objects in the image using OpenCV.
    Supports transparent backgrounds (Alpha thresholding) and solid color backgrounds.
    """
    # Load image using OpenCV (preserving alpha if exists)
    img_cv = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img_cv is None:
        raise ValueError(f"無法讀取圖片：{image_path}")
        
    h, w = img_cv.shape[:2]
    
    # 1. Generate Binary Mask
    has_alpha_channel = (img_cv.shape[-1] == 4)
    
    # Check if the alpha channel is actually used (i.e., not all 255)
    is_transparent = False
    if has_alpha_channel:
        alpha = img_cv[:, :, 3]
        if not np.all(alpha == 255):
            is_transparent = True
            
    if is_transparent:
        alpha = img_cv[:, :, 3]
        # Treat any pixel with alpha > 10 as foreground
        _, mask = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    else:
        # No active alpha channel. Convert to BGR (dropping alpha if any) and detect solid bg.
        if has_alpha_channel:
            img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGRA2BGR)
        else:
            img_rgb = img_cv
            
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2GRAY)
        
        # Take the top-left corner pixel as background candidate
        bg_val = int(gray[0, 0])
        # Find absolute difference
        diff = cv2.absdiff(gray, bg_val)
        
        # Threshold the difference (adaptive threshold or fixed threshold)
        _, mask = cv2.threshold(diff, 15, 255, cv2.THRESH_BINARY)
        
        # Perform morphology closing to clean up small holes in the foreground
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 2. Find Contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    initial_boxes = []
    for c in contours:
        x, y, cw, ch = cv2.boundingRect(c)
        # Filter out tiny noise contours
        if cw >= min_size and ch >= min_size:
            initial_boxes.append([x, y, x + cw, y + ch])
            
    if not initial_boxes:
        return [], mask
        
    # If solid background, fill the contours of the mask to prevent transparent holes inside the characters
    if not is_transparent:
        filled_mask = np.zeros_like(mask)
        cv2.drawContours(filled_mask, contours, -1, 255, thickness=cv2.FILLED)
        mask = filled_mask
        
    # 3. Merge close bounding boxes
    final_boxes = merge_boxes(initial_boxes, gap)
    
    # Sort bounding boxes top-to-bottom, left-to-right (natural reading order)
    # We can group boxes that are on roughly the same row (within 10% height tolerance)
    # and sort them horizontally.
    final_boxes = sorted(final_boxes, key=lambda b: (b[1], b[0]))
    
    # Refine sorting to make it grid-like (sort row-by-row)
    sorted_boxes = []
    while final_boxes:
        # Take the first box and find all boxes that share a similar y-level (vertical overlap)
        curr = final_boxes.pop(0)
        row = [curr]
        curr_h = curr[3] - curr[1]
        y_tolerance = curr_h * 0.5  # 50% height of current box
        
        remaining = []
        for box in final_boxes:
            # Check if y-ranges overlap significantly
            if abs(box[1] - curr[1]) < y_tolerance or (box[1] < curr[3] and box[3] > curr[1]):
                row.append(box)
            else:
                remaining.append(box)
                
        # Sort current row horizontally
        row = sorted(row, key=lambda b: b[0])
        sorted_boxes.extend(row)
        final_boxes = remaining
        
    # Optional: Draw debug bounding boxes to a file
    if debug_output:
        debug_img = img_cv.copy()
        for i, box in enumerate(sorted_boxes):
            cv2.rectangle(debug_img, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
            cv2.putText(debug_img, str(i + 1), (box[0] + 5, box[1] + 25), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.imwrite(debug_output, debug_img)
        
    return sorted_boxes, mask

def main():
    parser = argparse.ArgumentParser(
        description="電腦視覺自動貼圖邊緣識別與切圖工具 (Smart Auto Image Slicing Tool)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例 (Examples):
  # 互動模式 (帶領您設定與操作):
  python3 auto_slice_image.py
  
  # 命令行模式 - 自動偵測並切割圖片，忽略小於 10px 的雜訊，將間距小於 40px 的物件合併為同一張貼圖:
  python3 auto_slice_image.py input.png --gap 40 --min-size 10
  
  # 命令行模式 - 切割後將每張貼圖大小縮放至 240x240 像素，並在同目錄生成偵測框預覽圖 debug.png:
  python3 auto_slice_image.py input.png -s 240x240 -d debug.png
"""
    )
    
    parser.add_argument("image_path", nargs="?", help="輸入圖片的檔案路徑 (不填則進入互動模式)")
    parser.add_argument("-g", "--gap", type=int, default=30,
                        help="合併間距門檻 (像素)。若兩個物件距離小於此值，則會自動合併為同張圖。可用於防範文字/特效與本體被切開 (預設: 30)")
    parser.add_argument("--min-size", type=int, default=15,
                        help="忽略的最小物件寬高 (像素)。可用於過濾極小雜訊 (預設: 15)")
    parser.add_argument("-d", "--debug-image", help="選填。指定一個檔案路徑來儲存『偵測框標示預覽圖』(例如: debug.png)")
    parser.add_argument("-o", "--output-dir", help="輸出圖片的目錄路徑 (預設在輸入圖片同目錄下建立子資料夾)")
    parser.add_argument("-s", "--size", type=parse_size, help="輸出每張切圖的指定尺寸，格式為 寬x高 (例如: 240x240)")
    parser.add_argument("-m", "--resize-mode", choices=['stretch', 'fit', 'pad'], default='pad',
                        help="縮放模式: stretch (拉伸符合), fit (等比例縮小), pad (等比例縮小並填充背景，預設模式)")
    parser.add_argument("--pad-color", type=parse_color, default='transparent',
                        help="當縮放模式為 pad 時的填充背景顏色 (支援 'transparent', 'white', 'black' 或 '#ffffff' 等，預設為 transparent)")
    parser.add_argument("--gentab", action="store_true",
                        help="同時為每張切圖產生 96x74 像素的 LINE 標籤頁圖示 (tab image)")
    parser.add_argument("--remove-bg", action="store_true",
                        help="自動去除偵測到的背景，將背景區域轉為透明（適用於 JPG 或無透明度的 PNG）")
    
    args = parser.parse_args()

    # If no arguments are provided, switch to interactive mode
    is_interactive = len(sys.argv) == 1 or args.image_path is None
    
    if is_interactive:
        print("="*60)
        print("      歡迎使用電腦視覺自動貼圖邊緣識別與切圖工具")
        print("="*60)
        print("提示: 您可以直接將圖片拖曳至此終端機視窗中取得路徑。\n")
        
        # 1. Image path
        def validate_file(p):
            p = p.strip('\'"')
            if not os.path.isfile(p):
                raise ValueError("檔案路徑不存在，請重新輸入。")
            return p
        image_path = get_interactive_input("1. 請輸入或拖入圖片路徑: ", validator=validate_file)
        
        # 2. Gap size
        def validate_int_min_0(v):
            val = int(v)
            if val < 0:
                raise ValueError("數值必須大於或等於 0。")
            return val
        gap = get_interactive_input("2. 請設定合併間距 (像素) [貼圖主體與下方文字的距離，建議 20-50，預設 30]: ", 
                                    default_val=30, validator=validate_int_min_0)
                                    
        # 3. Minimum Noise Size
        min_size = get_interactive_input("3. 請設定忽略的最小物件寬高 (像素) [可用於過濾雜點，預設 15]: ", 
                                         default_val=15, validator=validate_int_min_0)
        
        # 4. Target size
        def validate_optional_size(v):
            if not v or v.lower() == 'none' or v.lower() == 'skip':
                return None
            return parse_size(v)
        size = get_interactive_input("4. 請輸入指定輸出尺寸 [寬x高] (例如 240x240，直接按 Enter 略過不縮放): ", default_val=None, validator=validate_optional_size)
        
        # 5. Resize mode and padding color if size specified
        resize_mode = 'pad'
        pad_color = (0, 0, 0, 0)
        if size:
            print("\n已設定指定輸出尺寸。請選擇縮放處理模式:")
            print("  [1] pad (等比例縮減並填充背景 - 推薦，不會變形，預設值)")
            print("  [2] fit (等比例縮減至邊界內 - 不填充背景，輸出圖片可能小於指定尺寸)")
            print("  [3] stretch (直接拉伸填滿 - 圖片可能會變形)")
            
            mode_choice = get_interactive_input("請選擇模式 [1/2/3] (預設 1): ", default_val='1')
            if mode_choice == '2':
                resize_mode = 'fit'
            elif mode_choice == '3':
                resize_mode = 'stretch'
            else:
                resize_mode = 'pad'
                
            if resize_mode == 'pad':
                pad_color = get_interactive_input(
                    "請輸入填充背景顏色 (支援 'transparent', 'white', 'black' 或十六進制 #ffffff，預設為 transparent): ",
                    default_val=(0, 0, 0, 0),
                    validator=parse_color
                )
        
        # 6. Generate Debug Preview Image
        gen_debug = get_interactive_input("5. 是否產生「偵測框標示預覽圖」供您檢查？ [y/N，預設 N]: ", default_val='n').strip().lower()
        debug_image = None
        if gen_debug.startswith('y'):
            dir_name = os.path.dirname(image_path)
            base_name = os.path.splitext(os.path.basename(image_path))[0]
            debug_image = os.path.join(dir_name, f"{base_name}_debug_boxes.png")
            
        # 7. Generate LINE Tab Image
        gen_tab = get_interactive_input("6. 是否要同時產生 96x74 的 LINE 標籤圖示 (tab image)？ [y/N，預設 N]: ", default_val='n').strip().lower()
        gentab = gen_tab.startswith('y')
        
        # 8. Remove Background
        rem_bg = get_interactive_input("7. 是否要自動去除偵測到的背景，將背景區域轉為透明？ [y/N，預設 N]: ", default_val='n').strip().lower()
        remove_bg = rem_bg.startswith('y')
        
        # 9. Output directory
        output_dir = get_interactive_input("8. 請輸入輸出資料夾路徑 (直接按 Enter 會在圖片旁建立同名資料夾): ", default_val=None)
    else:
        image_path = args.image_path.strip('\'"')
        gap = args.gap
        min_size = args.min_size
        debug_image = args.debug_image
        size = args.size
        resize_mode = args.resize_mode
        pad_color = args.pad_color
        output_dir = args.output_dir
        gentab = args.gentab
        remove_bg = args.remove_bg
        
        if not os.path.isfile(image_path):
            print(f"錯誤: 找不到輸入圖片檔案 '{image_path}'。")
            sys.exit(1)

    # Resolve default output directory
    if not output_dir:
        dir_name = os.path.dirname(image_path)
        base_name_without_ext = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(dir_name, f"{base_name_without_ext}_auto_slices")
    
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*50)
    print("正在以電腦視覺演算法偵測貼圖邊緣...")
    print(f"輸入檔案: {image_path}")
    print(f"合併間距: {gap} 像素")
    print(f"忽略雜訊: < {min_size}x{min_size} 像素")
    if size:
        print(f"輸出尺寸: {size[0]}x{size[1]} ({resize_mode} 模式)")
        if resize_mode == 'pad':
            print(f"填充背景: {pad_color}")
    else:
        print("輸出尺寸: 保持貼圖原始偵測邊界大小 (無損)")
    if remove_bg:
        print("背景處理: 自動偵測並去除背景（轉為透明）")
    if gentab:
        print("同時產生: 96x74 標籤頁圖示 (tab image)")
    print(f"輸出目錄: {output_dir}")
    if debug_image:
        print(f"偵測框預覽圖將儲存於: {debug_image}")
    print("="*50 + "\n")

    try:
        # Detect objects bounding boxes
        boxes, mask = detect_objects(image_path, min_size=min_size, gap=gap, debug_output=debug_image)
        
        if not boxes:
            print("錯誤: 未偵測到任何貼圖。請確認圖片是否非空白，或嘗試調整間距與雜訊過濾參數。")
            sys.exit(1)
            
        print(f"偵測成功！共識別出 {len(boxes)} 張貼圖。開始裁切與儲存...")
        
        # Load image with PIL to crop and resize cleanly
        img = Image.open(image_path)
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        digits = len(str(len(boxes)))
        
        saved_count = 0
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = box
            
            # Crop using PIL (box coordinates are x1, y1, x2, y2)
            slice_img = img.crop((x1, y1, x2, y2))
            
            # Remove background if requested
            if remove_bg:
                slice_img = slice_img.convert('RGBA')
                mask_crop = mask[y1:y2, x1:x2]
                mask_crop_pil = Image.fromarray(mask_crop).convert('L')
                r, g, b, a = slice_img.split()
                new_a = ImageChops.darker(a, mask_crop_pil)
                slice_img = Image.merge('RGBA', (r, g, b, new_a))
                
            # Save tab image if gentab is True (generate from cropped original)
            if gentab:
                tab_img = resize_image(slice_img, (96, 74), 'pad', (0, 0, 0, 0))
                tab_filename = f"{base_name}_auto_{i+1:0{digits}d}_tab.png"
                tab_output_path = os.path.join(output_dir, tab_filename)
                tab_img.save(tab_output_path, 'PNG', optimize=True)
                
            # Resize main image if specified
            if size:
                slice_img = resize_image(slice_img, size, resize_mode, pad_color)
                
            filename = f"{base_name}_auto_{i+1:0{digits}d}.png"
            output_path = os.path.join(output_dir, filename)
            
            # Save losslessly (PNG)
            slice_img.save(output_path, 'PNG', optimize=True)
            saved_count += 1
            if gentab:
                print(f"[{saved_count}/{len(boxes)}] 已儲存: {filename} ({slice_img.size[0]}x{slice_img.size[1]}) 與 {tab_filename} (96x74)")
            else:
                print(f"[{saved_count}/{len(boxes)}] 已儲存: {filename} ({slice_img.size[0]}x{slice_img.size[1]})")
            
        print("\n" + "="*50)
        print(f"處理完成！成功自動裁切並儲存 {saved_count} 張貼圖。")
        print(f"結果目錄: {output_dir}")
        if debug_image:
            print(f"提示: 請查看 [偵測框標示預覽圖]({debug_image}) 以檢查偵測是否完美。若有拆分過度或合併過度，可調整 --gap 參數。")
        print("="*50)
        
    except Exception as e:
        print(f"\n處理圖片時發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
