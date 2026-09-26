#!/bin/bash
# =============================================================================
# Helper Script สำหรับสั่งเทรนโมเดล XAUUSD บน Google Colab ผ่าน Colab CLI
# =============================================================================

echo "=========================================================="
echo "🚀 เริ่มต้นกระบวนการเชื่อมต่อและเทรนโมเดลบน Google Colab"
echo "=========================================================="

# 1. ตรวจสอบสถานะการล็อกอิน
echo "🔍 ตรวจสอบเซสชัน Google Colab..."
colab sessions

if [ $? -ne 0 ]; then
    echo "⚠️ กรุณายืนยันตัวตน (Login) ผ่านลิงก์ที่แสดงด้านบนก่อนใช้งาน"
    exit 1
fi

# 2. สั่งสร้าง Colab Session พร้อม GPU T4
echo "⚙️ กำลังขอเปิดเครื่อง Colab VM (GPU T4)..."
colab new --gpu T4 -s xauusd_train

# 3. อัปโหลด Pipeline Script
echo "📤 กำลังอัปโหลดไฟล์โค้ด pipeline.py ขึ้น Colab..."
colab upload -s xauusd_train /root/xauusd_ml_colab/pipeline.py

# 4. สั่งติดตั้งไลบรารีบน Colab VM
echo "📦 กำลังติดตั้ง lightgbm, scikit-learn บน Colab VM..."
colab install -s xauusd_train lightgbm scikit-learn pandas numpy joblib

# 5. สั่งรันเทรน
echo "🔥 เริ่มต้นเทรนโมเดลบน Colab..."
colab exec -s xauusd_train -f /root/xauusd_ml_colab/pipeline.py

# 6. ดาวน์โหลดโมเดลที่เทรนเสร็จแล้วกลับมาที่เครื่อง
echo "📥 กำลังดาวน์โหลดไฟล์โมเดลกลับมาเก็บในเครื่อง..."
colab download -s xauusd_train xauusd_upside_model.joblib /storage/emulated/0/Download/EA/
colab download -s xauusd_train xauusd_downside_model.joblib /storage/emulated/0/Download/EA/

# 7. ปิดเซสชันเพื่อประหยัดโควต้า
echo "🛑 กำลังปิดเซสชัน Colab VM..."
colab stop -s xauusd_train

echo "=========================================================="
echo "✅ เทรนเสร็จสมบูรณ์และบันทึกโมเดลไว้ที่ /storage/emulated/0/Download/EA/ เรียบร้อย!"
echo "=========================================================="
