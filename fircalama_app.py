import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import random
import os  # Import the 'os' module

# Sayfa ayarı (EN BAŞA TAŞINDI)
st.set_page_config(page_title="Diş Fırçalama Takip", layout="centered")

# Firebase'ı başlat (secrets içinden)
if not firebase_admin._apps:
    try:
        import json
        cred_dict = dict(st.secrets["firebase"])  # ✅ BU SATIR DÜZELTİLDİ
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        st.success("Firebase initialized successfully!")  # opsiyonel başarı mesajı
    except Exception as e:
        st.error(f"Firebase initialization failed: {e}")
        st.stop()  # Stop execution if Firebase fails to initialize

db = firestore.client()

# Renk teması
st.markdown("""
    <style>
        /* Menü arka plan rengi */
        .css-1d391kg { 
            background-color: 8E7DBE; 
        }
        /* Sayfa başlık rengi */
        .css-10trblm { 
            color: #2c3e50; 
        }
        /* Font rengi */
        .css-16huue1 { 
            color: #34495e; 
        }
        /* Sidebar başlık rengi */
        .css-1aumxhk { 
            color: #2980b9; 
        }
    </style>
""", unsafe_allow_html=True)

# Menü
st.sidebar.title("🔍 Menü")
sayfa = st.sidebar.selectbox("Bir sayfa seçin:", ["👶 Çocuk Seç veya Ekle", "📊 Profilim", "🏠 Giriş", "🕵 Takvim", "🏅 Rozetlerim", "🎁 Avatar Koleksiyonu", "🔒 Admin"])

# Firestore verileri çek
veri = {}
try:
    docs = db.collection("fircalama").stream()
    for doc in docs:
        veri[doc.id] = doc.to_dict()
except Exception as e:
    st.error(f"Error fetching data from Firestore: {e}")

cocuklar = list(veri.keys())
secilen_cocuk = st.session_state.get("aktif_cocuk")

# Üstte avatar ve isim göster
if sayfa not in ["👶 Çocuk Seç veya Ekle", "🔒 Admin"] and secilen_cocuk in veri:
    avatar = veri[secilen_cocuk].get("avatar", "")
    cols = st.columns([1, 6])
    with cols[0]:
        if avatar:
            st.image(avatar, width=60)
    with cols[1]:
        st.markdown(f"### {secilen_cocuk}", unsafe_allow_html=True)

# --- Aralıksız ay hesabı fonksiyonu ---
def hesapla_araliksiz_ay(baslangic, kayitlar):
    try:
        baslangic_tarih = datetime.strptime(baslangic, "%Y-%m-%d")
        bugun = datetime.today()
        toplam_ay = (bugun.year - baslangic_tarih.year) * 12 + (bugun.month - baslangic_tarih.year) + 1

        ay_sayaci = 0
        for ay_index in range(toplam_ay):
            ay_baslangic = baslangic_tarih + relativedelta(months=ay_index)
            ay_sonu = (ay_baslangic + relativedelta(months=1)) - timedelta(days=1)
            simdiki_ay = pd.date_range(ay_baslangic, ay_sonu)

            hepsi_var_mi = all(
                kayitlar.get(d.strftime("%Y-%m-%d"), {}).get("sabah") == "evet" and
                kayitlar.get(d.strftime("%Y-%m-%d"), {}).get("aksam") == "evet"
                for d in simdiki_ay
                if d <= bugun  # Gelecekteki tarihler dahil edilmesin
            )
            if hepsi_var_mi:
                ay_sayaci += 1
            else:
                break

        return ay_sayaci
    except Exception as e:
        st.error(f"Error in hesapla_araliksiz_ay: {e}")
        return 0

# --- En uzun üst üste gün ---
def max_ust_uste_gun(kayitlar):
    try:
        tarih_listesi = sorted(kayitlar.keys())
        max_seri = 0
        seri = 0
        onceki_tarih = None
        for tarih in tarih_listesi:
            bilgi = kayitlar[tarih]
            # 🔒 sadece sözlük ise devam et
            if isinstance(bilgi, dict) and bilgi.get("sabah") == "evet" and bilgi.get("aksam") == "evet":
                if onceki_tarih and (datetime.strptime(tarih, "%Y-%m-%d") - onceki_tarih).days == 1:
                    seri += 1
                else:
                    seri = 1
                max_seri = max(max_seri, seri)
                onceki_tarih = datetime.strptime(tarih, "%Y-%m-%d")
            else:
                seri = 0
                onceki_tarih = None
        return max_seri
    except Exception as e:
        st.error(f"Error in max_ust_uste_gun: {e}")
        return 0

# --- Son fırçalama tarihini bul ---
def son_fircalama_tarihi_bul(kayitlar):
    tarihler = sorted(kayitlar.keys(), reverse=True)
    for tarih in tarihler:
        bilgi = kayitlar.get(tarih, {})
        if isinstance(bilgi, dict) and bilgi.get("sabah") == "evet" and bilgi.get("aksam") == "evet":
            return tarih
    return None

# --- Başarımları sıfırla ---
def basarimlari_sifirla(secilen_cocuk):
    try:
        db.collection("fircalama").document(secilen_cocuk).update({
            "baslangic_tarihi": datetime.today().strftime("%Y-%m-%d")
        })
        st.success("Tüm başarımlar sıfırlandı!")
    except Exception as e:
        st.error(f"Başarımları sıfırlama hatası: {e}")

# 👶 ÇOCUK SEÇ VEYA EKLE
if sayfa == "👶 Çocuk Seç veya Ekle":
    st.title("👶 Çocuk Seç veya Yeni Ekle")

    secilen = st.selectbox("Çocuk seçin:", ["Yeni çocuk ekle"] + cocuklar)

    if secilen != "Yeni çocuk ekle":
        st.session_state["aktif_cocuk"] = secilen
        st.success(f"{secilen} seçildi. Artık diğer sayfalara geçebilirsin.")
    else:
        yeni_isim = st.text_input("Yeni çocuk ismi:").strip().capitalize()
        cinsiyet = st.radio("Cinsiyet:", ["kız", "erkek"], horizontal=True)

        if yeni_isim.lower() == "admin":
            st.session_state["aktif_cocuk"] = "admin"
            st.success("Admin ekranına erişim sağlandı. Artık Admin sayfasına geçebilirsiniz.")
        else:
            # Avatarları yükle
            avatarlar = {}

            try:
                ortak_doc = db.collection("avatarlar").document("ortak").get()
                if ortak_doc.exists:
                    avatarlar.update(ortak_doc.to_dict())

                cinsiyet_doc = db.collection("avatarlar").document(cinsiyet).get()
                if cinsiyet_doc.exists:
                    avatarlar.update(cinsiyet_doc.to_dict())
            except Exception as e:
                st.error(f"Error fetching avatars: {e}")

            # Başlangıçta sadece 0. aya kadar olanlar gösterilir
            uygun_avatarlar = {
                k: v for k, v in avatarlar.items()
                if isinstance(v, dict) and v.get("ay", 99) <= 0
            }

            # Rastgele üç avatar seç
            try:
                rastgele_avatarlar = random.sample(list(uygun_avatarlar.items()), min(3, len(uygun_avatarlar)))
            except ValueError:
                rastgele_avatarlar = []  # Handle the case where there are fewer than 3 avatars

            st.write("Avatar seçin:")
            secilen_avatar = None
            for k, v in rastgele_avatarlar:
                cols = st.columns([1, 6])
                with cols[0]:
                    st.image(v["url"], width=80)
                with cols[1]:
                    if st.checkbox(f"{k} ({v['ay']}. ayda açılır)", key=k):
                        secilen_avatar = k

            if secilen_avatar:
                avatar_url = uygun_avatarlar[secilen_avatar]["url"]

            if st.button("✅ Kaydet"):
                if yeni_isim and secilen_avatar:
                    try:
                        db.collection("fircalama").document(yeni_isim).set({
                            "avatar": avatar_url,
                            "cinsiyet": cinsiyet,
                            "baslangic_tarihi": datetime.today().strftime("%Y-%m-%d")
                        })
                        st.session_state["aktif_cocuk"] = yeni_isim
                        st.success(f"{yeni_isim} başarıyla eklendi ve seçildi.")
                    except Exception as e:
                        st.error(f"Error saving new child: {e}")
                else:
                    st.warning("İsim ve avatar seçilmelidir.")

# --- SAYFA: PROFİLİM ---
if sayfa == "📊 Profilim" and secilen_cocuk:
    st.title("📊 Profilim")
    kayitlar = veri.get(secilen_cocuk, {})
    if not isinstance(kayitlar, dict):
        kayitlar = {}

    # Son fırçalama tarihini bul
    son_fircalama_tarihi = son_fircalama_tarihi_bul(kayitlar)

    # Aralıksız ay sayısını hesapla
    aktif_ay = hesapla_araliksiz_ay(kayitlar.get("baslangic_tarihi", datetime.today().strftime("%Y-%m-%d")), kayitlar)
    en_uzun = max_ust_uste_gun(kayitlar)

    st.metric(label="🎯 Aralıksız Ay", value=f"{aktif_ay} ay")
    st.metric(label="🔥 En Uzun Seri", value=f"{en_uzun} gün")

    # Sıralama hesapla
def toplam_evet_sayisi(kayitlar):
    return sum(
        1 for _, v in kayitlar.items()
        if isinstance(v, dict) and v.get("sabah") == "evet" and v.get("aksam") == "evet"
    )

siralama_df = pd.DataFrame([
    {
        "isim": ad,
        "aktif_ay": hesapla_araliksiz_ay(v.get("baslangic_tarihi", datetime.today().strftime("%Y-%m-%d")), v),
        "uzun_seri": max_ust_uste_gun(v),
        "toplam_evet": toplam_evet_sayisi(v)
    }
    for ad, v in veri.items()
])

if sayfa == "📊 Profilim" and secilen_cocuk:
    # Öncelik: aktif_ay > uzun_seri > toplam_evet
    siralama_df = siralama_df.sort_values(
        by=["aktif_ay", "uzun_seri", "toplam_evet"],
        ascending=[False, False, False]
    ).reset_index(drop=True)
    siralama_df["sıra"] = siralama_df.index

    with st.expander("👨‍👩‍👧 Diğer Katılımcılar Sıralaması"):
        st.dataframe(
            siralama_df[["sıra", "isim", "aktif_ay", "uzun_seri", "toplam_evet"]]
            .rename(columns={
                "isim": "İsim",
                "aktif_ay": "Aralıksız Ay",
                "uzun_seri": "En Uzun Seri",
                "toplam_evet": "Toplam Tam Gün"
            })
        )

# 🏠 GİRİŞ SAYFASI
if sayfa == "🏠 Giriş":
    st.title("📋 Yeni Kayıt Girişi")

    if not secilen_cocuk:
        st.warning("Lütfen önce bir çocuk seçin.")
    else:
        # 3 gün fırçalama uyarısı (Giriş sayfasında)
        kayitlar = veri.get(secilen_cocuk, {})
        if not isinstance(kayitlar, dict):
            kayitlar = {}

        son_fircalama_tarihi = son_fircalama_tarihi_bul(kayitlar)
        if son_fircalama_tarihi:
            son_tarih = datetime.strptime(son_fircalama_tarihi, "%Y-%m-%d").date()
            fark = (datetime.now().date() - son_tarih).days
            if fark > 3:
                st.error(
                    "Son 3 gündür dişlerini fırçalamadığın için aralıksız fırçalama sayacın sıfırlandı! "
                    "Tüm başarımların gitti :("
                )
                basarimlari_sifirla(secilen_cocuk)

        tarih = st.date_input("Tarih:", value=datetime.today())
        tarih_str = tarih.strftime("%Y-%m-%d")
        sabah = st.radio("Sabah fırçaladı mı?", ["evet", "hayır"], horizontal=True)
        aksam = st.radio("Akşam fırçaladı mı?", ["evet", "hayır"], horizontal=True)

        if st.button("⏱ 2 Dakikalık Kronometre"):
            with st.empty():
                for i in range(120, 0, -1):
                    mins, secs = divmod(i, 60)
                    st.markdown(f"<h2 style='text-align:center;'>⏳ {mins:02d}:{secs:02d}</h2>", unsafe_allow_html=True)
                    time.sleep(1)
                st.markdown("<h2 style='text-align:center; color:green;'>✅ Süre doldu! Aferin!</h2>", unsafe_allow_html=True)

        if st.button("✅ Kaydet"):
            try:
                mevcut_veri = veri.get(secilen_cocuk, {})
                mevcut_veri[tarih_str] = {"sabah": sabah, "aksam": aksam}
                db.collection("fircalama").document(secilen_cocuk).set(mevcut_veri)
                st.success(f"{secilen_cocuk} için {tarih_str} günü kaydedildi.")
                if sabah == "evet" or aksam == "evet":
                    st.markdown("<h1 style='text-align: center; color: green;'>🎉 Başardın! 🎉</h1>", unsafe_allow_html=True)

                # Rozet kontrolü
                kayitlar = mevcut_veri
                baslangic_tarihi = kayitlar.get("baslangic_tarihi", datetime.today().strftime("%Y-%m-%d"))
                toplam_ay = hesapla_araliksiz_ay(baslangic_tarihi, kayitlar)

                rozetler = [
                    (18, "🏆 1.5 Yıllık Şampiyon Rozeti (18 ay)"),
                    (12, "🥇 1 Yıllık Altın Rozet (12 ay)"),
                    (11, "🥈 11 Aylık Gümüş Rozet"),
                    (10, "🥉 10 Aylık Bronz Rozet"),
                    (9, "🌟 9 Aylık Yıldız Rozet"),
                    (8, "🌼 8 Aylık Çiçek Rozet"),
                    (7, "🌈 7 Aylık Gökkuşağı Rozet"),
                    (6, "🔥 6 Aylık Ateş Rozet"),
                    (5, "💎 5 Aylık Elmas Rozet"),
                    (4, "🍀 4 Aylık Şans Rozet"),
                    (3, "🎉 3 Aylık Kutlama Rozet"),
                    (2, "✨ 2 Aylık Parıltı Rozet"),
                    (1, "🌟 1 Aylık Başlangıç Rozet")
                ]

                kazanilan_rozetler = [rozet for ay, rozet in rozetler if toplam_ay >= ay]
                if kazanilan_rozetler:
                    son_kazanilan_rozet = kazanilan_rozetler[0]
                    st.balloons()
                    st.success(f"🎉 {son_kazanilan_rozet} kazandın! Tebrikler! 🎉")
            except Exception as e:
                st.error(f"Error saving data: {e}")

# 🕵 TAKVİM SAYFASI
if sayfa == "🕵 Takvim":
    st.title("📆 Aylık Fırçalama Takvimi")

    if not secilen_cocuk:
        st.warning("Lütfen önce bir çocuk seçin.")
    else:
        yil = st.number_input("Yıl:", value=datetime.today().year, step=1)
        ay = st.number_input("Ay (1-12):", min_value=1, max_value=12, value=datetime.today().month, step=1)

        df = pd.DataFrame([
            {"Tarih": (datetime(yil, ay, 1) + timedelta(days=i)).strftime("%Y-%m-%d")}
            for i in range(31)
            if (datetime(yil, ay, 1) + timedelta(days=i)).month == ay
        ])
        df["Sabah"] = ""
        df["Akşam"] = ""

        kayitlar = veri.get(secilen_cocuk, {})
        for i, row in df.iterrows():
            bilgi = kayitlar.get(row["Tarih"], {})
            df.at[i, "Sabah"] = bilgi.get("sabah", "")
            df.at[i, "Akşam"] = bilgi.get("aksam", "")

        bugun = datetime.today().strftime("%Y-%m-%d")
        def vurgula(satir): return ["background-color: lightgreen"] * len(satir) if satir["Tarih"] == bugun else ["" for _ in satir]
        st.dataframe(df.style.apply(vurgula, axis=1), use_container_width=True)

# 🏅 ROZETLERİM SAYFASI
if sayfa == "🏅 Rozetlerim":
    st.title("🏅 Rozetlerim")

    if not secilen_cocuk:
        st.warning("Lütfen önce bir çocuk seçin.")
    else:
        kayitlar = veri.get(secilen_cocuk, {})
        ust_uste = 0
        max_ust_uste = 0

        for gun in sorted(kayitlar):
            bilgi = kayitlar.get(gun, {})
            if isinstance(bilgi, dict) and bilgi.get("sabah") == "evet" and bilgi.get("aksam") == "evet":
                ust_uste += 1
                max_ust_uste = max(max_ust_uste, ust_uste)
            else:
                ust_uste = 0

        # Rozetler için ay hesaplama
        baslangic_tarihi = kayitlar.get("baslangic_tarihi", datetime.today().strftime("%Y-%m-%d"))
        toplam_ay = hesapla_araliksiz_ay(baslangic_tarihi, kayitlar)

        # Tüm rozetler
        rozetler = [
            (18, "🏆 1.5 Yıllık Şampiyon Rozeti (18 ay)"),
            (12, "🥇 1 Yıllık Altın Rozet (12 ay)"),
            (11, "🥈 11 Aylık Gümüş Rozet"),
            (10, "🥉 10 Aylık Bronz Rozet"),
            (9, "🌟 9 Aylık Yıldız Rozet"),
            (8, "🌼 8 Aylık Çiçek Rozet"),
            (7, "🌈 7 Aylık Gökkuşağı Rozet"),
            (6, "🔥 6 Aylık Ateş Rozet"),
            (5, "💎 5 Aylık Elmas Rozet"),
            (4, "🍀 4 Aylık Şans Rozet"),
            (3, "🎉 3 Aylık Kutlama Rozet"),
            (2, "✨ 2 Aylık Parıltı Rozet"),
            (1, "🌟 1 Aylık Başlangıç Rozet")
        ]

        kazanilan_rozetler = [rozet for ay, rozet in rozetler if toplam_ay >= ay]

        if kazanilan_rozetler:
            st.markdown(f"### {secilen_cocuk} için toplam aralıksız ay: {toplam_ay} ay")
            st.markdown("## 🎖 Kazanılan Rozetler:")
            for rozet in kazanilan_rozetler:
                st.markdown(f"- {rozet}")
        else:
            st.markdown("### Henüz rozet kazanılmadı.")

# 🎁 AVATAR KOLEKSİYONU
if sayfa == "🎁 Avatar Koleksiyonu":
    st.title("🎁 Avatar Koleksiyonu")

    if not secilen_cocuk:
        st.warning("Lütfen önce bir çocuk seçin.")
    else:
        kayitlar = veri.get(secilen_cocuk, {})
        aktif_ay = hesapla_araliksiz_ay(kayitlar.get("baslangic_tarihi", datetime.today().strftime("%Y-%m-%d")), kayitlar)
        cinsiyet = veri.get(secilen_cocuk, {}).get("cinsiyet", "kiz") or "kiz"

        avatarlar = {}
        for c in [cinsiyet, "ortak"]:
            if c:  # boş değilse hata almayız
                try:
                    doc = db.collection("avatarlar").document(c).get()
                    if doc.exists:
                        avatarlar.update(doc.to_dict())
                except Exception as e:
                    st.error(f"Error fetching avatars for gender {c}: {e}")

        if avatarlar:
            st.markdown(f"### {aktif_ay}. aya kadar açılan avatarlar")
            if "secilen_avatar" not in st.session_state:
                st.session_state["secilen_avatar"] = None

            for isim, info in avatarlar.items():
                url = info.get("url")
                ay = info.get("ay", 1)
                cols = st.columns([1, 5, 2])
                with cols[0]:
                    st.image(url, width=80)
                with cols[1]:
                    if ay > aktif_ay:
                        st.caption(f"🔒 {isim} - {ay}. ayda açılır")
                    else:
                        st.markdown(f"**{isim}** - Açık")
                with cols[2]:
                    if ay <= aktif_ay:
                        if st.button("Seç", key=f"select_{isim}"):
                            st.session_state["secilen_avatar"] = isim

            if st.session_state["secilen_avatar"]:
                yeni_avatar_url = avatarlar[st.session_state["secilen_avatar"]]["url"]
                if st.button("Avatarı Güncelle"):
                    try:
                        db.collection("fircalama").document(secilen_cocuk).update({"avatar": yeni_avatar_url})
                        st.success(f"Avatar başarıyla **{st.session_state['secilen_avatar']}** olarak güncellendi!")
                    except Exception as e:
                        st.error(f"Error updating avatar: {e}")
        else:
            st.warning("Hiç avatar bulunamadı.")

# 🔒 ADMIN PANELİ
ADMIN_PASSWORD = os.environ.get("firca123")  # Retrieve from environment variable

if "aktif_cocuk" in st.session_state and st.session_state["aktif_cocuk"] == "admin":
    if sayfa == "🔒 Admin":
        st.title("🔒 Admin Panel")
        sifre = st.text_input("Admin şifresi", type="password")

        if sifre == ADMIN_PASSWORD:
            st.success("Admin girişi başarılı.")

            cinsiyet = st.radio("Avatarı hangi gruba eklemek istersin?", ["kiz", "erkek", "ortak"], horizontal=True)
            avatar_adi = st.text_input("Yeni avatarın adı:")
            avatar_url = st.text_input("Avatar görsel URL'si:")
            acilan_ay = st.number_input("Kaçıncı ayda açılsın? (0 = Başlangıç)", min_value=0, max_value=18, value=0)

            if st.button("➕ Avatar Ekle"):
                if avatar_adi and avatar_url:
                    try:
                        doc_ref = db.collection("avatarlar").document(cinsiyet)
                        doc_ref.set({
                            avatar_adi: {"url": avatar_url, "ay": acilan_ay}
                        }, merge=True)
                        st.success(f"{avatar_adi} başarıyla eklendi! {acilan_ay}. ayda açılacak.")
                    except Exception as e:
                        st.error(f"Error adding avatar: {e}")
                else:
                    st.warning("Lütfen tüm alanları doldurun.")

            st.markdown("---")
            try:
                mevcut_avatarlar = db.collection("avatarlar").document(cinsiyet).get().to_dict() or {}
            except Exception as e:
                st.error(f"Error fetching existing avatars: {e}")
                mevcut_avatarlar = {}

            if mevcut_avatarlar:
                secilen_avatar = st.selectbox("Düzenlemek veya silmek istediğiniz avatarı seçin:", list(mevcut_avatarlar.keys()))
                if secilen_avatar:
                    yeni_avatar_adi = st.text_input("Yeni avatar adı:", value=secilen_avatar)
                    yeni_avatar_url = st.text_input("Yeni avatar görsel URL'si:", value=mevcut_avatarlar[secilen_avatar].get("url", ""))
                    yeni_acilan_ay = st.number_input("Yeni açılma ayı:", min_value=0, max_value=18, value=mevcut_avatarlar[secilen_avatar].get("ay", 0))

                    if st.button("💾 Avatarı Güncelle"):
                        if yeni_avatar_adi and yeni_avatar_url:
                            try:
                                doc_ref = db.collection("avatarlar").document(cinsiyet)
                                doc_ref.update({
                                    secilen_avatar: firestore.DELETE_FIELD,  # Eski avatarı sil
                                    yeni_avatar_adi: {"url": yeni_avatar_url, "ay": yeni_acilan_ay}  # Yeni avatarı ekle
                                })
                                st.success(f"{secilen_avatar} başarıyla güncellendi!")
                            except Exception as e:
                                st.error(f"Error updating avatar: {e}")
                        else:
                            st.warning("Lütfen tüm alanları doldurun.")

                    if st.button("❌ Avatarı Sil"):
                        try:
                            doc_ref = db.collection("avatarlar").document(cinsiyet)
                            doc_ref.update({secilen_avatar: firestore.DELETE_FIELD})
                            st.success(f"{secilen_avatar} başarıyla silindi!")
                        except Exception as e:
                            st.error(f"Error deleting avatar: {e}")
            else:
                st.info("Seçilen grupta düzenlenecek veya silinecek avatar bulunamadı.")
        else:
            st.info("Yönetici giriş ekranı.")
