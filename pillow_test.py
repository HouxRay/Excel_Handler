from PIL import Image

def jpg_to_ico(jpg_path, ico_path, sizes=None):
    """
    将 JPG 图片转换为 ICO 格式的图标文件。
    
    参数：
    - jpg_path: JPG 图片的路径（如 "input.jpg"）
    - ico_path: 输出的 ICO 文件路径（如 "output.ico"）
    - sizes: 图标尺寸列表（如 [(16,16), (32,32), (48,48)]），默认为 [(32,32)]
    """
    if sizes is None:
        sizes = [(32, 32)]  # 默认尺寸为 32x32
    
    # 打开 JPG 图片
    with Image.open(jpg_path) as img:
        # 确保图片是 RGB 模式（ICO 支持 RGB/RGBA）
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 生成多尺寸图标（可选）
        # 如果只保存单一尺寸，直接使用 img.resize()
        images = []
        for size in sizes:
            # 调整图片尺寸并保持高质量缩放
            resized_img = img.copy()
            resized_img.thumbnail(size, Image.LANCZOS)
            images.append(resized_img)
        
        # 保存为 ICO 格式
        images[0].save(  # 以第一个尺寸为主
            ico_path,
            format='ico',
            append_images=images[1:] if len(images) > 1 else [],  # 添加其他尺寸
            save_all=True  # 保存多尺寸图标
        )

# 示例：将 input.jpg 转换为包含 16x16, 32x32, 48x48 的 ICO 文件
jpg_to_ico("pic.jpg", "output.ico", sizes=[(16, 16), (32, 32), (48, 48)])