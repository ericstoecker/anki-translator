import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface Props {
  words: string[];
  onWordSelected: (word: string) => void;
  deckId: string;
}

export default function WordSelectPage({
  words,
  onWordSelected,
  deckId,
}: Props) {
  const [checking, setChecking] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<{
    word: string;
    explanation: string;
    duplicate_of_id?: string;
  } | null>(null);
  const navigate = useNavigate();

  if (words.length === 0) {
    return (
      <div className="page">
        <h1>Select a Word</h1>
        <p>No words extracted. Go back to take a photo.</p>
        <button className="btn btn-secondary" onClick={() => navigate("/")}>
          Back to Camera
        </button>
      </div>
    );
  }

  const handleWordClick = async (word: string) => {
    if (!deckId) {
      onWordSelected(word);
      navigate("/translate");
      return;
    }

    // Check for duplicates first
    setChecking(word);
    setDuplicate(null);
    try {
      const result = await api.checkDuplicate({
        word,
        deck_id: deckId,
        source_language: "", // Will be derived from deck
      });
      if (result.is_duplicate) {
        setDuplicate({
          word,
          explanation:
            result.explanation || "This word may already exist in your deck.",
          duplicate_of_id: result.duplicate_of_id,
        });
      } else {
        onWordSelected(word);
        navigate("/translate");
      }
    } catch {
      // If duplicate check fails, proceed anyway
      onWordSelected(word);
      navigate("/translate");
    } finally {
      setChecking(null);
    }
  };

  const proceedAnyway = () => {
    if (duplicate) {
      onWordSelected(duplicate.word);
      navigate("/translate");
    }
  };

  return (
    <div className="page">
      <h1>Select a Word</h1>
      <p style={{ marginBottom: "8px", color: "#666" }}>
        Tap a word to translate it.
      </p>

      <div className="word-grid">
        {words.map((word, i) => (
          <button
            key={i}
            className={`word-btn ${checking === word ? "selected" : ""}`}
            onClick={() => handleWordClick(word)}
            disabled={checking !== null}
          >
            {word}
          </button>
        ))}
      </div>

      {checking && <div className="loading">Checking for duplicates...</div>}

      {duplicate && (
        <div className="duplicate-warning">
          <h3>Possible Duplicate</h3>
          <p>{duplicate.explanation}</p>
          <div className="duplicate-actions">
            <button
              className="btn btn-primary btn-small"
              onClick={proceedAnyway}
            >
              Proceed Anyway
            </button>
            <button
              className="btn btn-secondary btn-small"
              onClick={() => setDuplicate(null)}
            >
              Choose Different Word
            </button>
          </div>
        </div>
      )}

      <button className="btn btn-secondary" onClick={() => navigate("/")}>
        Back to Camera
      </button>
    </div>
  );
}
