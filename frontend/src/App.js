import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

const transitionOptions = [
  'fade',
  'slide_left',
  'slide_right',
  'slide_top',
  'slide_bottom',
  'zoom',
  'typewriter',
  'glitch',
  'rotate',
];

const imageEffectOptions = [
  'depth_zoom',
  'ken_burns',
  'color_grade',
  'light_leaks',
  'film_grain',
  'vignette',
  'motion_overlay',
];

function App() {
  const [images, setImages] = useState([]);
  const [music, setMusic] = useState(null);
  const [duration, setDuration] = useState(4);
  const [loading, setLoading] = useState(false);
  const [slides, setSlides] = useState([
    { text: '', position: '', darkening: '', duration: '', transition: '', effect: '' },
  ]);

  const handleSlideChange = (index, field, value) => {
    const updated = [...slides];
    updated[index][field] = value;
    setSlides(updated);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData();
    slides.forEach(slide => {
      formData.append('texts', slide.text);
      formData.append('positions', slide.position);
      formData.append('darkening', slide.darkening);
      formData.append('duration', slide.duration); // May be blank
      formData.append('transitions', slide.transition);
      formData.append('image_effects', slide.effect);
    });
    images.forEach(img => formData.append('images', img));
    if (music) formData.append('music', music);
    formData.append('duration', duration);

    try {
      const response = await axios.post('http://localhost:8000/api/create-slideshow/', formData, {
        responseType: 'blob',
      });

      const blob = new Blob([response.data], { type: 'video/mp4' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'slideshow.mp4');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      // Optionally, setDownloadLink(url) if you want to show it as well.
    } catch (err) {
      console.error(err);
      alert('Video generation failed!');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <h1 className="title">🎉 Create Your Slideshow</h1>
      <form onSubmit={handleSubmit} className="form">
        <div className="section orange">
          <h2>Slide Texts</h2>
          {slides.map((slide, i) => (
            <div key={i} style={{ marginBottom: '1rem' }}>
              <textarea
                placeholder={`Slide Text ${i + 1}`}
                value={slide.text}
                onChange={(e) => handleSlideChange(i, 'text', e.target.value)}
                rows={3}
              />
              <input
                type="number"
                placeholder="Vertical % (0–100, optional)"
                value={slide.position}
                onChange={(e) => handleSlideChange(i, 'position', e.target.value)}
              />
              <input
                type="number"
                step="0.1"
                min="0"
                max="1"
                value={slide.darkening}
                onChange={(e) => handleSlideChange(i, 'darkening', e.target.value)}
                placeholder="Darkening Level (0 to 1)"
              />
              <input
                type="number"
                placeholder="Duration (seconds)"
                value={slide.duration}
                onChange={(e) => handleSlideChange(i, 'duration', e.target.value)}
              />
              <select
                value={slide.transition}
                onChange={(e) => handleSlideChange(i, 'transition', e.target.value)}
              >
                <option value="">Random</option>
                {transitionOptions.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <select
                value={slide.effect}
                onChange={(e) => handleSlideChange(i, 'effect', e.target.value)}
              >
                <option value="">None</option>
                {imageEffectOptions.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              setSlides([
                ...slides,
                { text: '', position: '', darkening: '', duration: '', transition: '', effect: '' },
              ])
            }
          >
            ➕ Add Another Slide
          </button>
        </div>

        <div className="section blue">
          <h2>⏱ Slide Duration (seconds)</h2>
          <input type="number" value={duration} onChange={(e) => setDuration(e.target.value)} />
        </div>

        <div className="section green">
          <h2>🖼 Upload Images</h2>
          <input type="file" multiple accept="image/*" onChange={(e) => setImages([...e.target.files])} />
        </div>

        <div className="section pink">
          <h2>🎵 Upload Background Music</h2>
          <input type="file" accept="audio/*" onChange={(e) => setMusic(e.target.files[0])} />
        </div>

        <button className="submit" type="submit" disabled={loading}>
          {loading ? 'Processing...' : '🚀 Generate Video'}
        </button>
      </form>
    </div>
  );
}

export default App;