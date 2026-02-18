import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

interface Props {
  word: string;
  deckId: string;
}

export default function TranslatePage({ word, deckId }: Props) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [cardData, setCardData] = useState<{
    note_type_id: string;
    fields: Record<string, string>;
    translation: Record<string, string>;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [addingNative, setAddingNative] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!word) return;
    loadTranslation();
  }, [word]);

  const loadTranslation = async () => {
    setLoading(true);
    setError("");
    try {
      // Use format-card which does both translation and formatting
      const result = await api.formatCard({
        word,
        source_language: "", // Derived from deck
        target_language: "", // Derived from deck
        deck_id: deckId,
      });
      setCardData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async () => {
    if (!cardData) return;
    setSaving(true);
    try {
      const result = await api.createCard({
        deck_id: deckId,
        note_type_id: cardData.note_type_id,
        fields: cardData.fields,
        source_word: word,
      });
      // Accept it immediately (mark as pending_sync)
      await api.acceptCard(result.id);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save card");
    } finally {
      setSaving(false);
    }
  };

  const handleAddNativeTranslation = async () => {
    setAddingNative(true);
    try {
      const user = await api.getMe();
      if (!user.native_language) {
        setError("Please set your native language in Settings first.");
        return;
      }
      // Re-translate with native language
      const result = await api.formatCard({
        word,
        source_language: "",
        target_language: "",
        deck_id: deckId,
        native_language: user.native_language,
      });
      setCardData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add native translation");
    } finally {
      setAddingNative(false);
    }
  };

  if (!word) {
    return (
      <div className="page">
        <h1>Translate</h1>
        <p>No word selected.</p>
        <button className="btn btn-secondary" onClick={() => navigate("/words")}>
          Back to Words
        </button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Translating</h1>
        <div className="loading">Translating "{word}" and formatting card...</div>
      </div>
    );
  }

  if (saved) {
    return (
      <div className="page">
        <h1>Card Created</h1>
        <p style={{ marginBottom: "16px", color: "#2e7d32" }}>
          Card for "{word}" has been created and is pending sync to Anki.
        </p>
        <div style={{ display: "flex", gap: "8px" }}>
          <button className="btn btn-primary" onClick={() => navigate("/words")}>
            Translate Another Word
          </button>
          <button className="btn btn-secondary" onClick={() => navigate("/")}>
            New Photo
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Card Preview</h1>

      {error && <div className="error">{error}</div>}

      {cardData && (
        <>
          <div className="card-preview">
            {Object.entries(cardData.fields).map(([name, value]) => (
              <div className="field" key={name}>
                <div className="field-name">{name}</div>
                <div className="field-value">{value}</div>
              </div>
            ))}
          </div>

          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            <button
              className="btn btn-primary"
              onClick={handleAccept}
              disabled={saving}
            >
              {saving ? "Saving..." : "Accept Card"}
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleAddNativeTranslation}
              disabled={addingNative}
            >
              {addingNative ? "Adding..." : "Add Native Translation"}
            </button>
            <button className="btn btn-danger btn-small" onClick={() => navigate("/words")}>
              Reject
            </button>
          </div>
        </>
      )}
    </div>
  );
}
