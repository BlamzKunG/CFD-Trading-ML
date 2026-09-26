#!/usr/bin/env python3
import sys
import os

print("Installing onnxmltools and onnx...")
os.system("pip install -q onnxmltools onnx skl2onnx lightgbm")

import lightgbm as lgb
from onnxmltools import convert_lightgbm
from onnxmltools.convert.common.data_types import FloatTensorType

print("Loading models...")
model_up = lgb.Booster(model_file='/content/xauusd_upside_model.txt')
model_down = lgb.Booster(model_file='/content/xauusd_downside_model.txt')

# Set input shape [1, 22] for MT5
initial_type = [('input', FloatTensorType([1, 22]))]

print("Converting Upside model to ONNX...")
onnx_up = convert_lightgbm(model_up, initial_types=initial_type, target_opset=12)
with open('/content/xauusd_upside.onnx', 'wb') as f:
    f.write(onnx_up.SerializeToString())

print("Converting Downside model to ONNX...")
onnx_down = convert_lightgbm(model_down, initial_types=initial_type, target_opset=12)
with open('/content/xauusd_downside.onnx', 'wb') as f:
    f.write(onnx_down.SerializeToString())

print("✅ ONNX models generated successfully!")
