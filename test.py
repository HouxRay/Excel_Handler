import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import cv2

img = np.array(Image.open('D:\\output\\002400\\RGT_01.tif')).astype(np.uint8)

plt.imshow(img)  # 显示图像数据
plt.show()       # 弹出窗口