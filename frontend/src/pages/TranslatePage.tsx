import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TranslationOption } from "../api/client";

interface Props {
  word: string;
  deckId: string;
}

type Phase = "translating" | "choosing" | "formatting" | "preview" | "saved";

export default function TranslatePage({ word, deckId }: Props) {
  const [phase, setPhase] = useState<Phase>("translating");
  const [error, setError] = useState("");
  const [translations, setTranslations] = useState<TranslationOption[]>([]);
  const [chosenTranslation, setChosenTranslation] = useState<TranslationOption | null>(null);
  const [cardData, setCardData] = useState<{
    note_type_id: string;
    fields: Record<string, string>;
  } | null>(null);
  const [saving, setSaving] = useState(false);
  const [addingNative, setAddingNative] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!word) return;
    loadTranslations();
  }, [word]);

  const loadTranslations = async () => {
    setPhase("translating");
    setError("");
    try {
      const result = await api.translate({
        word,
        source_language: "",
        target_language: "",
        deck_id: deckId,
      });
      setTranslations(result.translations);
      if (result.translations.length === 1) {
        // Auto-advance if only one option
        await formatWithTranslation(result.translations[0]);
      } else {
        setPhase("choosing");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Translation failed");
      setPhase("choosing");
    }
  };

  const formatWithTranslation = async (option: TranslationOption, nativeLanguage?: string) => {
    setChosenTranslation(option);
    setPhase("formatting");
    setError("");
    try {
      const result = await api.formatCard({
        deck_id: deckId,
        word: option.word,
        translation: option.translation,
        part_of_speech: option.part_of_speech,
        context: option.context,
        native_language: nativeLanguage,
      });
      setCardData(result);
      setPhase("preview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Card formatting failed");
      setPhase("choosing");
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
      await api.acceptCard(result.id);
      setPhase("saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save card");
    } finally {
      setSaving(false);
    }
  };

  const handleAddNativeTranslation = async () => {
    if (!chosenTranslation) return;
    setAddingNative(true);
    try {
      const user = await api.getMe();
      if (!user.native_language) {
        setError("Please set your native language in Settings first.");
        return;
      }
      await formatWithTranslation(chosenTranslation, user.native_language);
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

  if (phase === "translating") {
    return (
      <div className="page">
        <h1>Translating</h1>
        <div className="loading">Translating "{word}"...</div>
      </div>
    );
  }

  if (phase === "choosing") {
    return (
      <div className="page">
        <h1>Choose Translation</h1>
        <p>Select the correct translation for "<strong>{word}</strong>":</p>

        {error && <div className="error">{error}</div>}

        <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px" }}>
          {translations.map((opt, i) => (
            <button
              key={i}
              className="btn btn-primary"
              style={{ textAlign: "left", padding: "12px" }}
              onClick={() => formatWithTranslation(opt)}
            >
              <strong>{opt.translation}</strong>
              {opt.part_of_speech && <span style={{ opacity: 0.7 }}> ({opt.part_of_speech})</span>}
              {opt.context && (
                <div style={{ fontSize: "0.85em", opacity: 0.8, marginTop: "4px" }}>
                  {opt.context}
                </div>
              )}
            </button>
          ))}
        </div>

        <button className="btn btn-secondary" onClick={() => navigate("/words")}>
          Back to Words
        </button>
      </div>
    );
  }

  if (phase === "formatting") {
    return (
      <div className="page">
        <h1>Formatting Card</h1>
        <div className="loading">Formatting card for "{word}"...</div>
      </div>
    );
  }

  if (phase === "saved") {
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

  // phase === "preview"
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
