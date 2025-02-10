a = [0,1,2,3,4,5,6]


print(a[1:3])

def test_image_processing():
    """测试图像处理功能"""
    # 测试图像路径使用.bmp格式
    test_image = "test_image.bmp"
    
    # 读取测试图像
    img = read_bmp(test_image)
    if img is None:
        print("无法读取测试图像")
        return False
    
    # 处理图像
    processed_img = process_image(img)
    
    # 保存处理后的图像
    save_bmp("processed_" + test_image, processed_img)
    
    return True