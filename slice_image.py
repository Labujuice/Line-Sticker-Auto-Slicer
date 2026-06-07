#!/usr/bin/env python3
import os
import sys
import argparse
from PIL import Image, ImageColor

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
        # ImageColor.getcolor returns RGB or RGBA depending on specifier.
        # We enforce RGBA output.
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
        # Fit inside without padding (aspect ratio preserved)
        if aspect_img > aspect_target:
            new_w = target_w
            new_h = max(1, int(target_w / aspect_img))
        else:
            new_h = target_h
            new_w = max(1, int(target_h * aspect_img))
        return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
    elif mode == 'pad':
        # Fit inside with padding (aspect ratio preserved, padded to exact target_size)
        if aspect_img > aspect_target:
            new_w = target_w
            new_h = max(1, int(target_w / aspect_img))
        else:
            new_h = target_h
            new_w = max(1, int(target_h * aspect_img))
            
        resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Determine background image mode
        # If padding color is not opaque or original image has transparency, use RGBA
        if pad_color_rgba[3] < 255 or img.mode == 'RGBA':
            background = Image.new('RGBA', (target_w, target_h), pad_color_rgba)
        else:
            background = Image.new(img.mode, (target_w, target_h), pad_color_rgba[:3] if img.mode == 'RGB' else pad_color_rgba)
            
        # Center the resized image
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        
        # Paste using resized image as mask if it has an alpha channel
        if resized_img.mode == 'RGBA':
            background.paste(resized_img, (offset_x, offset_y), resized_img)
        else:
            background.paste(resized_img, (offset_x, offset_y))
            
        return background
    
    return img

def main():
    parser = argparse.ArgumentParser(
        description="圖片無損切圖與縮放工具 (Image Slicing & Resizing Tool)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例 (Examples):
  # 互動模式 (將引導您輸入所有必要資訊):
  python3 slice_image.py
  
  # 命令行模式 - 將圖片切成 4x4 的網格並儲存至預設目錄:
  python3 slice_image.py input.png -c 4 -r 4
  
  # 命令行模式 - 切成 2x3 網格，並將每張切圖縮放到 240x240 像素，超出部分透明填充:
  python3 slice_image.py input.png -c 2 -r 3 -s 240x240 -m pad --pad-color transparent
  
  # 命令行模式 - 切成 2x2 網格，縮小至 100x100 像素，使用白色背景填充，儲存至指定目錄:
  python3 slice_image.py input.png -c 2 -r 2 -s 100x100 -m pad --pad-color white -o ./output_folder
"""
    )
    
    parser.add_argument("image_path", nargs="?", help="輸入圖片的檔案路徑 (不填則進入互動模式)")
    parser.add_argument("-c", "--cols", type=int, help="橫向切分數量 (列數/Columns)，必須大於等於 1")
    parser.add_argument("-r", "--rows", type=int, help="縱向切分數量 (行數/Rows)，必須大於等於 1")
    parser.add_argument("-o", "--output-dir", help="輸出圖片的目錄路徑 (預設在輸入圖片同目錄下建立子資料夾)")
    parser.add_argument("-s", "--size", type=parse_size, help="輸出每張切圖的指定尺寸，格式為 寬x高 (例如: 240x240)")
    parser.add_argument("-m", "--resize-mode", choices=['stretch', 'fit', 'pad'], default='pad',
                        help="縮放模式: stretch (拉伸符合), fit (等比例縮放至邊界內), pad (等比例縮小並填充背景，預設模式)")
    parser.add_argument("--pad-color", type=parse_color, default='transparent',
                        help="當縮放模式為 pad 時的填充背景顏色 (支援 'transparent', 'white', 'black', '#ffffff' 等，預設為 transparent)")
    
    args = parser.parse_args()

    # If no arguments are provided, switch to interactive mode
    is_interactive = len(sys.argv) == 1 or args.image_path is None
    
    if is_interactive:
        print("="*60)
        print("          歡迎使用圖片無損切圖與縮放工具")
        print("="*60)
        print("提示: 您可以直接將圖片拖曳至此終端機視窗中取得路徑。\n")
        
        # 1. Image path
        def validate_file(p):
            p = p.strip('\'"')  # strip terminal quotes
            if not os.path.isfile(p):
                raise ValueError("檔案路徑不存在，請重新輸入。")
            return p
        
        image_path = get_interactive_input("1. 請輸入或拖入圖片路徑: ", validator=validate_file)
        
        # 2. Columns
        def validate_int_min_1(v):
            val = int(v)
            if val < 1:
                raise ValueError("數量必須大於或等於 1。")
            return val
        
        cols = get_interactive_input("2. 請輸入水平切分數量 (欄數 / Columns, 預設為 1): ", default_val=1, validator=validate_int_min_1)
        
        # 3. Rows
        rows = get_interactive_input("3. 請輸入垂直切分數量 (列數 / Rows, 預設為 1): ", default_val=1, validator=validate_int_min_1)
        
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
        
        # 6. Output directory
        output_dir = get_interactive_input("5. 請輸入輸出資料夾路徑 (直接按 Enter 會在圖片旁建立同名資料夾): ", default_val=None)
    else:
        image_path = args.image_path.strip('\'"')
        cols = args.cols if args.cols is not None else 1
        rows = args.rows if args.rows is not None else 1
        size = args.size
        resize_mode = args.resize_mode
        pad_color = args.pad_color
        output_dir = args.output_dir
        
        # Validate CLI inputs
        if not os.path.isfile(image_path):
            print(f"錯誤: 找不到輸入圖片檔案 '{image_path}'。")
            sys.exit(1)
        if cols < 1 or rows < 1:
            print("錯誤: 切分欄數與列數必須大於或等於 1。")
            sys.exit(1)

    # Resolve default output directory
    if not output_dir:
        dir_name = os.path.dirname(image_path)
        base_name_without_ext = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(dir_name, f"{base_name_without_ext}_slices")
    
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n" + "="*50)
    print("開始處理圖片...")
    print(f"輸入檔案: {image_path}")
    print(f"切分格數: {cols} 欄 (Columns) x {rows} 列 (Rows) = 共 {cols * rows} 張切圖")
    if size:
        print(f"輸出尺寸: {size[0]}x{size[1]} ({resize_mode} 模式)")
        if resize_mode == 'pad':
            print(f"填充背景: {pad_color}")
    else:
        print("輸出尺寸: 保持切圖原始解析度 (無損)")
    print(f"輸出目錄: {output_dir}")
    print("="*50 + "\n")

    try:
        # Load image
        img = Image.open(image_path)
        img_w, img_h = img.size
        print(f"原始圖片尺寸: {img_w}x{img_h} ({img.mode})")
        
        # Calculate coordinate boundaries for precise splitting
        x_coords = [int(i * img_w / cols) for i in range(cols + 1)]
        y_coords = [int(j * img_h / rows) for j in range(rows + 1)]
        
        col_digits = len(str(cols))
        row_digits = len(str(rows))
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        
        saved_count = 0
        
        for r in range(rows):
            for c in range(cols):
                box = (x_coords[c], y_coords[r], x_coords[c+1], y_coords[r+1])
                
                # Verify standard box dimensions
                box_w = box[2] - box[0]
                box_h = box[3] - box[1]
                if box_w <= 0 or box_h <= 0:
                    continue
                
                # Crop
                slice_img = img.crop(box)
                
                # Resize if specified
                if size:
                    slice_img = resize_image(slice_img, size, resize_mode, pad_color)
                
                # Form filename using 1-based indexing
                # Format: name_r01_c01.png
                filename = f"{base_name}_r{r+1:0{row_digits}d}_c{c+1:0{col_digits}d}.png"
                output_path = os.path.join(output_dir, filename)
                
                # Save losslessly (PNG is lossless and supports transparency)
                slice_img.save(output_path, 'PNG', optimize=True)
                
                saved_count += 1
                print(f"[{saved_count}/{cols * rows}] 已儲存: {filename} ({slice_img.size[0]}x{slice_img.size[1]})")
                
        print("\n" + "="*50)
        print(f"處理完成！成功切分並儲存 {saved_count} 張圖片。")
        print(f"結果目錄: {output_dir}")
        print("="*50)
        
    except Exception as e:
        print(f"\n處理圖片時發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
