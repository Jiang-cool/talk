import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 导入主应用
from app import app

# Vercel 需要这个变量
handler = app