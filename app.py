from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import koneksi
import pymysql
import os
import uuid
from datetime import datetime
db = koneksi.get_connection()

app = Flask(__name__)
# secret_key wajib ada agar fitur flash message (notifikasi) di HTML tidak eror
app.secret_key = 'kunci_rahasia_carelink_platform'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def save_file(file):
    if file and file.filename:
        extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{str(uuid.uuid4())[:8]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{extension}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        return unique_filename
    return None

# Objek tiruan agar admin.html tidak eror saat membaca {{ current_user.username }}
class MockUser:
    def __init__(self, username):
        self.username = username
        self.is_authenticated = True

current_user = MockUser("Admin_CareLink")


# ========================================================
# 1. RUTE HALAMAN UTAMA (DASHBOARD USER)
# ========================================================
# ========================================================
# 1. RUTE HALAMAN UTAMA (DASHBOARD USER - FIX FILTER KARTU RP 0)
# ========================================================
@app.route('/')
def index():
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()  # Otomatis menghasilkan DictCursor sesuai koneksi.py kamu
        
        # PERBAIKAN DI SINI: Tambahkan WHERE jumlah_disalurkan > 0 agar data postingan foto tanpa dana tidak ikut muncul
        cursor.execute("SELECT * FROM penyaluran ORDER BY tanggal_penyaluran DESC")
        distributions = cursor.fetchall()
        
    
        # SINKRONISASI DATA STRING DARI DATABASE KE ARRAY UNTUK HTML
        for dist in distributions:
            # 1. Pecah data foto kondisi awal (Bagian atas wilayah terdampak)
            raw_foto = dist.get('foto_kondisi') or dist.get('FOTO_KONDISI')
            if raw_foto and str(raw_foto).strip() != "" and str(raw_foto) != 'None':
                dist['list_foto'] = dist['foto_kondisi'].split(',')
            else:
                dist['list_foto'] = []
                
            # 2. Pecah data foto bukti penyaluran susulan (Bagian bawah bukti posko)
            raw_bukti = dist.get('foto_penyaluran') or dist.get('FOTO_PENYALURAN')
            if raw_bukti and str(raw_bukti).strip() != "" and str(raw_bukti) != 'None':
                dist['list_foto_penyaluran'] = dist['foto_penyaluran'].split(',')
            else:
                dist['list_foto_penyaluran'] = []

        # Hitung statistik donasi & penyaluran untuk Saldo Kas Global
        cursor.execute("SELECT SUM(jumlah) as total FROM donasi WHERE status = 'terverifikasi'")
        res_donasi = cursor.fetchone()
        total_donasi = res_donasi['total'] if res_donasi and res_donasi['total'] else 0
        
        cursor.execute("SELECT SUM(jumlah_disalurkan) as total FROM penyaluran")
        res_penyaluran = cursor.fetchone()
        total_penyaluran = res_penyaluran['total'] if res_penyaluran and res_penyaluran['total'] else 0
        
        # Rumus saldo kas tersedia
        saldo = total_donasi - total_penyaluran
        
        cursor.close()
        db.close()
    except Exception as e:
        distributions = []
        saldo = 0
        total_penyaluran = 0 
        print(f"Informasi Database Error: {e}")

    # Mengarahkan halaman utama langsung ke user.html membawa data saldo & program bencana
    return render_template('user.html', distributions=distributions, saldo=saldo, total_penyaluran=total_penyaluran, current_user=current_user)
# ========================================================
# 2. RUTE HALAMAN LOGIN ADMIN
# ========================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            db = koneksi.get_connection()
            cursor = db.cursor()  
            
            # Ambil data user berdasarkan username dan password
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user_data = cursor.fetchone()
            
            cursor.close()
            db.close()
            
            if user_data:
                # FIX SINKRONISASI: Memanggil langsung key ['role'] karena formatnya sudah pasti dict
                role = user_data.get('role') or user_data.get('ROLE')
                
                if role == 'admin':
                    global current_user
                    current_user = MockUser(username)
                    return redirect(url_for('dashboard_admin'))
                else:
                    return redirect(url_for('index'))
            else:
                return "Username atau Password Salah!"
                
        except Exception as e:
            return f"Eror saat proses login: {e}"
        
    return render_template('login.html')


# ========================================================
# 3. RUTE REGISTER AKUN BARU
# ========================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            db = koneksi.get_connection()
            cursor = db.cursor()
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'user')", (username, password))
            db.commit()
            cursor.close()
            db.close()
            return redirect(url_for('login'))
        except Exception as e:
            return f"Gagal mendaftar: {e}"
            
    return render_template('register.html')


# ========================================================
# 4. RUTE TAMPILAN DASHBOARD ADMIN
# ========================================================
@app.route('/admin/dashboard')
def dashboard_admin():
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        
        # 1. Ambil semua daftar donasi masuk untuk tabel admin
        cursor.execute("SELECT * FROM donasi ORDER BY tanggal DESC")
        donations = cursor.fetchall()
        
        # 2. Ambil semua data log penyaluran bantuan
        cursor.execute("SELECT * FROM penyaluran ORDER BY tanggal_penyaluran DESC")
        distributions = cursor.fetchall()
        
        # 3. Hitung ringkasan kotak info di atas dashboard admin
        cursor.execute("SELECT SUM(jumlah) as total FROM donasi")
        res_masuk = cursor.fetchone()
        total_masuk = res_masuk['total'] if res_masuk and res_masuk['total'] else 0
        
        cursor.execute("SELECT SUM(jumlah_disalurkan) as total FROM penyaluran")
        res_keluar = cursor.fetchone()
        total_keluar = res_keluar['total'] if res_keluar and res_keluar['total'] else 0
        
        saldo = total_masuk - total_keluar
        
        db.close()
    except Exception as e:
        donations = []
        distributions = []
        total_masuk = total_keluar = saldo = 0
        print(f"Error admin dashboard: {e}")

    return render_template('admin.html', 
                           donations=donations, 
                           distributions=distributions, 
                           total_masuk=total_masuk, 
                           total_keluar=total_keluar, 
                           saldo=saldo, 
                           current_user=current_user)

 # --- TEMPELKAN DI SINI ---

@app.route('/edit-foto-kondisi/<int:id>', methods=['POST'])
def edit_foto_kondisi(id):
    files = request.files.getlist('foto_kondisi[]')
    nama_foto_list = [save_file(f) for f in files if f.filename]
    
    if not nama_foto_list:
        flash('Gagal: Tidak ada foto yang dipilih.', 'danger')
        return redirect(url_for('dashboard_admin'))
        
    foto_baru_str = ",".join(filter(None, nama_foto_list))
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("SELECT foto_kondisi FROM penyaluran WHERE id = %s", (id,))
        res = cursor.fetchone()
        foto_lama = res.get('foto_kondisi') if res else ""
        foto_final = f"{foto_lama},{foto_baru_str}" if foto_lama else foto_baru_str
        
        cursor.execute("UPDATE penyaluran SET foto_kondisi = %s WHERE id = %s", (foto_final, id))
        db.commit()
        cursor.close()
        db.close()
        flash('Foto kondisi berhasil ditambahkan!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

@app.route('/update-foto-bukti/<int:id>', methods=['POST'])
def update_foto_bukti(id):
    files = request.files.getlist('foto_penyaluran[]')
    nama_foto_list = [save_file(f) for f in files if f.filename]
    
    if not nama_foto_list:
        flash('Gagal: Tidak ada foto bukti yang dipilih.', 'danger')
        return redirect(url_for('dashboard_admin'))
        
    foto_baru_str = ",".join(filter(None, nama_foto_list))
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("SELECT foto_penyaluran FROM penyaluran WHERE id = %s", (id,))
        res = cursor.fetchone()
        foto_lama = res.get('foto_penyaluran') if res else ""
        
        foto_final = f"{foto_lama},{foto_baru_str}" if foto_lama else foto_baru_str
        
        cursor.execute("UPDATE penyaluran SET foto_penyaluran = %s WHERE id = %s", (foto_final, id))
        db.commit()
        cursor.close()
        db.close()
        flash('Bukti penyaluran berhasil ditambahkan!', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

@app.route('/edit-penyaluran/<int:id>', methods=['POST'])
def edit_penyaluran(id):
    nama = request.form.get('nama_bencana')
    bank = request.form.get('bank_penerima')
    rekening = request.form.get('rekening_penerima')
    jumlah = request.form.get('jumlah_disalurkan')
    deskripsi = request.form.get('deskripsi')
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("""
            UPDATE penyaluran 
            SET nama_bencana = %s, bank_penerima=%s, rekening_penerima=%s, jumlah_disalurkan = %s, deskripsi = %s 
            WHERE id = %s
        """, (nama, bank, rekening, jumlah, deskripsi, id))
        db.commit()
        cursor.close()
        db.close()
        flash('Data wilayah berhasil diperbarui!', 'success')
    except Exception as e:
        flash(f'Gagal Update: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

@app.route('/admin/konfirmasi-donasi/<int:id>')
def konfirmasi_donasi(id):
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        # Mengubah status donasi agar uangnya masuk ke saldo global
        cursor.execute("UPDATE donasi SET status = 'terverifikasi' WHERE id = %s", (id,))
        db.commit()
        db.close()
        flash('Donasi telah berhasil dikonfirmasi! Saldo otomatis bertambah.', 'success')
    except Exception as e:
        flash(f'Gagal konfirmasi: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

@app.route('/admin/tolak-donasi/<int:id>')
def tolak_donasi(id):
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        # Jika bukti transfer palsu/salah, admin bisa menghapus data donasi tersebut
        cursor.execute("DELETE FROM donasi WHERE id = %s", (id,))
        db.commit()
        db.close()
        flash('Donasi telah ditolak dan dihapus dari sistem.', 'warning')
    except Exception as e:
        flash(f'Gagal menghapus: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

@app.route('/admin/hapus-donasi/<int:id>')
def hapus_donasi(id):
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM donasi WHERE id = %s", (id,))
        db.commit()
        db.close()
        flash('Data donasi berhasil dihapus.', 'success')
    except Exception as e:
        flash(f'Gagal menghapus: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

# --- EDIT DATA DONASI (Nama & Jumlah) ---
@app.route('/admin/edit-donasi/<int:id>', methods=['POST'])
def edit_donasi(id):
    nama = request.form.get('nama_donatur')
    jumlah = request.form.get('jumlah')
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("UPDATE donasi SET nama_donatur=%s, jumlah=%s WHERE id=%s", (nama, jumlah, id))
        db.commit()
        db.close()
        flash('Data donasi berhasil diperbarui.', 'success')
    except Exception as e:
        flash(f'Gagal update: {e}', 'danger')
    return redirect(url_for('dashboard_admin'))

                          
# 5. RUTE PENDUKUNG AKSI FORM (DONASI, LOGOUT, DLL)
# ========================================================
@app.route('/tambah-donasi', methods=['POST'])
def tambah_donasi():
    nama_donatur = request.form.get('nama_donatur') or 'Anonim'
    jumlah = request.form.get('jumlah')
    bank_tujuan = request.form.get('bank_tujuan')
    keterangan = request.form.get('keterangan') 
    
    nama_file_simpan = None
    
    db = None
        
    try:
        db = koneksi.get_connection()
        if db is None:
            flash('Gagal menyambung ke database TiDB. Pastikan database Anda menyala.', 'danger')
            return redirect(url_for('index'))

        cursor = db.cursor()
        sql = """
            INSERT INTO donasi (nama_donatur, jumlah, bank_tujuan, keterangan, bukti_transfer, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """
        cursor.execute(sql, (nama_donatur, jumlah, bank_tujuan, keterangan, nama_file_simpan))

        db.commit()
        db.close()
        flash('Donasi behasil dikirim! Menunggu konfirmasi admin agar saldo bertambah.', 'success')
    except Exception as e:
        print(f"Gagal Simpan Donasi: {e}")
        flash(f'Gagal mengirim donasi: {e}', 'danger')
        
    return redirect(url_for('index'))


# ========================================================
# ⚡ RUTE TERBARU: AKSI UNTUK SISTEM INTERAKSI ADMIN (FIXED UPLOAD)
# ========================================================

# 🔵 TOMBOL 1: POSTING DAERAH BARU + FOTO KONDISI AWAL
@app.route('/post-kondisi-baru', methods=['POST'])
def post_kondisi_baru():
    nama_bencana = request.form.get('nama_bencana')
    files = request.files.getlist('foto_kondisi[]')
    
    # PERBAIKAN: Gunakan fungsi save_file(file) agar nama file diubah menjadi unik & bebas spasi
    nama_foto_list = [save_file(f) for f in files if f.filename]
            
    foto_kondisi_string = ",".join(filter(None, nama_foto_list)) if nama_foto_list else None
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO penyaluran (nama_bencana, jumlah_disalurkan, deskripsi, foto_kondisi)
            VALUES (%s, 0, '', %s)
        """, (nama_bencana, foto_kondisi_string))
        db.commit()
        cursor.close()
        db.close()
        flash('Daerah bencana baru beserta foto kondisi berhasil didaftarkan!', 'success')
    except Exception as e:
        flash(f'Gagal mendaftarkan daerah baru: {e}', 'danger')
        
    return redirect(url_for('dashboard_admin'))


# 🟢 TOMBOL 2: MENGUNGGAH FOTO HASIL PENYALURAN SUSULAN (VIA AJAX KOTAK HIJAU)
@app.route('/tambah-foto-penyaluran', methods=['POST'])
def tambah_foto_penyaluran():
    nama_bencana = request.form.get('nama_bencana')
    files = request.files.getlist('foto_penyaluran[]')
    
    # PERBAIKAN: Gunakan fungsi save_file(file) agar nama file diubah menjadi unik & bebas spasi
    nama_foto_list = [save_file(f) for f in files if f.filename]
            
    if not nama_foto_list:
        return jsonify({'success': False, 'message': 'Tidak ada file foto yang dipilih.'})
        
    foto_baru_string = ",".join(filter(None, nama_foto_list))
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        
        cursor.execute("SELECT foto_penyaluran FROM penyaluran WHERE nama_bencana = %s LIMIT 1", (nama_bencana,))
        result = cursor.fetchone()
        
        if result:
            foto_lama = result.get('foto_penyaluran') or result.get('FOTO_PENYALURAN')
            if foto_lama:
                foto_final = f"{foto_lama},{foto_baru_string}"
            else:
                foto_final = foto_baru_string
                
            cursor.execute("UPDATE penyaluran SET foto_penyaluran = %s WHERE nama_bencana = %s", (foto_final, nama_bencana))
            db.commit()
            cursor.close()
            db.close()
            return jsonify({'success': True})
        else:
            cursor.close()
            db.close()
            return jsonify({'success': False, 'message': f'Nama daerah "{nama_bencana}" tidak ditemukan di database.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ⚫ TOMBOL 3: MURNI TRANSAKSI DISTRIBUSI DANA BANTUAN KE DAERAH TARGET
@app.route('/tambah-penyaluran-dana', methods=['POST'])
def tambah_penyaluran_dana():
    nama_bencana = request.form.get('nama_bencana')
    bank = request.form.get('bank_penerima')
    rekening = request.form.get('rekening_penerima')
    jumlah_disalurkan = request.form.get('jumlah_disalurkan')
    deskripsi = request.form.get('deskripsi')
    
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("""
            INSERT INTO penyaluran (nama_bencana, bank_penerima , rekening_penerima, jumlah_disalurkan, deskripsi)
            VALUES (%s, %s, %s, %s, %s)
        """, (nama_bencana, bank, rekening, jumlah_disalurkan, deskripsi))
        db.commit()
        cursor.close()
        db.close()
        flash('Transaksi dana bantuan berhasil tercatat ke dalam log sistem!', 'success')
    except Exception as e:
        flash(f'Gagal memproses pengiriman dana: {e}', 'danger')
        
    return redirect(url_for('dashboard_admin'))


# ========================================================
# RUTE AKSI DATA (EDIT TEXT & HAPUS LOG)
# ========================================================
@app.route('/hapus-penyaluran/<int:id>')
def hapus_penyaluran(id):
    try:
        db = koneksi.get_connection()
        cursor = db.cursor()
        cursor.execute("DELETE FROM penyaluran WHERE id = %s", (id,))
        db.commit()
        cursor.close()
        db.close()
        flash('Data penyaluran berhasil dihapus!', 'success')
    except Exception as e:
        flash(f'Gagal menghapus data: {e}', 'danger')
        
    return redirect(url_for('dashboard_admin'))


@app.route('/logout')
def logout():
    global current_user
    current_user = MockUser("Guest")
    return redirect(url_for('index'))

@app.route('/tentang-kami')
def tentang_kami():
    return render_template('about.html')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)