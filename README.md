# ApacheAuto - Apache Server Monitoring System

Sistem monitoring otomatis untuk Apache web server yang memantau log, filesystem, dan mengirimkan notifikasi.

## Fitur

- Monitoring log Apache secara real-time
- Monitoring filesystem untuk perubahan file penting
- Database logging untuk analisis historis
- Sistem notifikasi yang dapat dikonfigurasi
- Dukungan systemd service

## Instalasi

1. Clone repository ini
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Copy `.env.example` ke `.env` dan sesuaikan konfigurasi:
```bash
cp .env.example .env
```

4. Edit `config.yaml` sesuai dengan kebutuhan Anda

5. Jalankan aplikasi:
```bash
python main.py
```

## Konfigurasi

- `config.yaml`: Konfigurasi utama aplikasi
- `.env`: Konfigurasi environment variables (sensitive data)

## Struktur Proyek

```
apacheauto/
├── README.md
├── requirements.txt
├── config.yaml
├── .env.example
├── main.py
├── apache_monitor/
│   ├── __init__.py
│   ├── log_monitor.py
│   ├── fs_monitor.py
│   ├── notifier.py
│   ├── db.py
│   └── utils.py
├── logs/
├── tests/
│   └── test_log_parsing.py
└── systemd/
    └── apache-monitor.service
```

## Lisensi

MIT License

