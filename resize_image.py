#!/usr/bin/env python3
import os
import sys
import argparse
from PIL import Image, ImageColor

def parse_size(size_str):
    """Parse size string in WIDTHxHEIGHT format."""
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
        if pad_color_rgba[3] < 255 or img.mode == 'RGBA':
            background = Image.new('RGBA', (target_w, target_h), pad_color_rgba)
        else:
            background = Image.new(img.mode, (target_w, target_h), pad_color_rgba[:3] if img.mode == 'RGB' else pad_color_rgba)
            
        # Center the resized image
        offset_x = (target_w - new_w) // 2
        offset_y = (target_h - new_h) // 2
        
        if resized_img.mode == 'RGBA':
            background.paste(resized_img, (offset_x, offset_y), resized_img)
        else:
            background.paste(resized_img, (offset_x, offset_y))
            
        return background
    
    return img

def main():
    parser = argparse.ArgumentParser(
        description="單張圖片縮放與透明填補工具 (Single Image Resizing Tool)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例 (Examples):
  # 將一張貼圖縮小到 240x240，超出部分用透明填充，預設輸出為 input_resized.png:
  python3 resize_image.py input.png -s 240x240
  
  # 一鍵將指定的貼圖 (如 01.png) 生成 LINE 規範的封面圖 (main.png, 240x240) 與標籤圖 (tab.png, 96x74):
  python3 resize_image.py 01.png --gencover
  
  # 縮小到 240x240，使用白色背景填充，儲存至指定的輸出路徑:
  python3 resize_image.py input.png -s 240x240 -m pad --pad-color white -o output.png
"""
    )
    
    parser.add_argument("image_path", help="輸入圖片的檔案路徑")
    parser.add_argument("-s", "--size", type=parse_size,
                        help="指定輸出尺寸，格式為 寬x高 (例如: 240x240)。如果未使用 --gencover，則此項為必填")
    parser.add_argument("-o", "--output", help="選填。輸出圖片檔案路徑 (預設在原檔名後加上 _resized，使用 --gencover 時無效)")
    parser.add_argument("-m", "--mode", choices=['stretch', 'fit', 'pad'], default='pad',
                        help="縮放模式: stretch (拉伸), fit (等比例縮放), pad (等比例縮放並填補背景，預設模式)")
    parser.add_argument("--pad-color", type=parse_color, default='transparent',
                        help="當縮放模式為 pad 時的填充背景顏色 (支援 'transparent', 'white', 'black' 或 '#ffffff'，預設為 transparent)")
    parser.add_argument("--gencover", action="store_true",
                        help="一鍵生成 LINE 貼圖所需的封面圖 main.png (240x240) 與標籤圖 tab.png (96x74)")
    
    args = parser.parse_args()
    
    # Validation
    if not args.gencover and not args.size:
        parser.error("當未使用 --gencover 時，必須指定 -s/--size 參數。")
        
    image_path = args.image_path.strip('\'"')
    if not os.path.isfile(image_path):
        print(f"錯誤: 找不到輸入圖片檔案 '{image_path}'。")
        sys.exit(1)
        
    # Resolve default output path
    if not args.output:
        dir_name = os.path.dirname(image_path)
        base_name, ext = os.path.splitext(os.path.basename(image_path))
        output_path = os.path.join(dir_name, f"{base_name}_resized.png")
    else:
        output_path = os.path.abspath(args.output)
        
    try:
        img = Image.open(image_path)
        print(f"原始尺寸: {img.size[0]}x{img.size[1]} ({img.mode})")
        
        if args.gencover:
            dir_name = os.path.dirname(image_path)
            if not dir_name:
                dir_name = "."
                
            main_path = os.path.join(dir_name, "main.png")
            tab_path = os.path.join(dir_name, "tab.png")
            
            # Generate main.png (240x240, pad mode, transparent)
            main_img = resize_image(img, (240, 240), 'pad', (0, 0, 0, 0))
            main_img.save(main_path, 'PNG', optimize=True)
            print(f"已生成封面圖: {main_path} (240x240)")
            
            # Generate tab.png (96x74, pad mode, transparent)
            tab_img = resize_image(img, (96, 74), 'pad', (0, 0, 0, 0))
            tab_img.save(tab_path, 'PNG', optimize=True)
            print(f"已生成標籤圖: {tab_path} (96x74)")
            
        else:
            resized_img = resize_image(img, args.size, args.mode, args.pad_color)
            # Save losslessly (PNG)
            resized_img.save(output_path, 'PNG', optimize=True)
            print(f"處理完成！已儲存至: {output_path} ({resized_img.size[0]}x{resized_img.size[1]})")
            
    except Exception as e:
        print(f"縮放圖片時發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
