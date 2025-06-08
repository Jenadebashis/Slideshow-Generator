# 🎞️ Slideshow Generator

This project generates slideshow videos from user-provided images and text, with optional background music. It's designed to be simple, fast, and accessible through a web interface.

---

## 🚀 Features

- Upload multiple images
- Add custom text for each slide
- Upload background music (optional)
- Auto-generate a downloadable slideshow video
- Built with Python (MoviePy) + React

---

## 🛠️ Tech Stack

- **Frontend:** React, Axios
- **Backend:** Python, Django REST Framework
- **Video Engine:** MoviePy

---

## 📦 Installation

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Set the `IMAGEMAGICK_BINARY` environment variable if ImageMagick isn't in your `PATH`. MoviePy relies on this tool for rendering text, so missing or misconfigured paths will cause errors like `MoviePy Error: creation of None failed`.

### Frontend

```bash
cd frontend
npm install
npm start
```

### Running Tests

Backend tests require the dependencies from `requirements.txt`:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py test
```

The frontend tests rely on `react-scripts`, installed via `npm install`:

```bash
cd frontend
npm test
```
