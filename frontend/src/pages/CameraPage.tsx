import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface Props {
  onWordsExtracted: (words: string[]) => void;
}

export default function CameraPage({ onWordsExtracted }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");
    setLoading(true);
    try {
      const result = await api.ocr(file);
      onWordsExtracted(result.words);
      navigate("/words");
    } catch (err) {
      setError(err instanceof Error ? err.message : "OCR failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <h1>Take a Photo</h1>
      <p style={{ marginBottom: "16px", color: "#666" }}>
        Photograph text from a book, menu, or sign to extract words.
      </p>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleFile}
        style={{ display: "none" }}
      />

      <button
        className="btn btn-primary"
        onClick={() => fileRef.current?.click()}
        disabled={loading}
        style={{ width: "100%", padding: "20px", fontSize: "1.1rem" }}
      >
        {loading ? "Extracting words..." : "Take Photo"}
      </button>

      <div style={{ marginTop: "12px" }}>
        <input
          type="file"
          accept="image/*"
          onChange={handleFile}
          style={{ width: "100%" }}
        />
        <p style={{ fontSize: "0.8rem", color: "#999", marginTop: "4px" }}>
          Or select an existing image
        </p>
      </div>

      {error && <div className="error">{error}</div>}
    </div>
  );
}
