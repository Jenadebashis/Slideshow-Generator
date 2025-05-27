import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [texts, setTexts] = useState(['']);
  const [images, setImages] = useState([]);
  const [music, setMusic] = useState(null);
  const [duration, setDuration] = useState(4);
  const [loading, setLoading] = useState(false);

  const handleTextChange = (index, value) => {
    const newTexts = [...texts];
    newTexts[index] = value;
    setTexts(newTexts);
  };

  const addTextField = () => setTexts([...texts, '']);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData();
    texts.forEach(text => formData.append('texts', text));
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
          {texts.map((text, i) => (
            <textarea
              key={i}
              placeholder={`Slide Text ${i + 1}`}
              value={text}
              onChange={(e) => handleTextChange(i, e.target.value)}
              rows={3}
            />
          ))}
          <button type="button" onClick={addTextField}>➕ Add Another Slide</button>
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