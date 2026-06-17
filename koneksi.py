import os
from dotenv import load_dotenv
import pymysql  # atau mysql.connector

# Memuat isi file .env
load_dotenv()

def get_connection():
    return pymysql.connect(
        host='gateway01.ap-southeast-1.prod.alicloud.tidbcloud.com',
        user='ap6J3yMMqSgQz7F.root',
        password='YzxGPY3O2FKUztyG',
        database='penyalurandonasi',
        port=4000,
        ssl_verify_cert=True,
        ssl_verify_identity=True,
        cursorclass=pymysql.cursors.DictCursor
    )

if __name__ == "__main__":
    try:
        print("Sedang mencoba menghubungkan ke TiDB Cloud...")
        test = get_connection()
        print("✅ KONEKSI BERHASIL! Aplikasi sudah tersambung ke TiDB.")
        test.close()
    except Exception as e:
        print("❌ KONEKSI GAGAL!")
        print(f"Pesan Eror: {e}")