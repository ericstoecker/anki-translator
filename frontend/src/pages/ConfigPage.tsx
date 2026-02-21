import { useEffect, useState } from "react";
import { api } from "../api/client";

interface Deck {
  id: string;
  name: string;
  source_language: string | null;
  target_language: string | null;
}

interface Props {
  selectedDeckId: string;
  onDeckChange: (id: string) => void;
}

export default function ConfigPage({ selectedDeckId, onDeckChange }: Props) {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [nativeLanguage, setNativeLanguage] = useState("");
  const [sourceLang, setSourceLang] = useState("");
  const [targetLang, setTargetLang] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    const deck = decks.find((d) => d.id === selectedDeckId);
    if (deck) {
      setSourceLang(deck.source_language || "");
      setTargetLang(deck.target_language || "");
    }
  }, [selectedDeckId, decks]);

  const loadData = async () => {
    try {
      const [deckList, user] = await Promise.all([
        api.listDecks(),
        api.getMe(),
      ]);
      setDecks(deckList);
      setNativeLanguage(user.native_language || "");
      if (!selectedDeckId && deckList.length > 0) {
        onDeckChange(deckList[0].id);
      }
    } catch {
      // ignore
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage("");
    try {
      await api.updateMe(nativeLanguage);
      if (selectedDeckId) {
        await api.updateDeck(selectedDeckId, {
          source_language: sourceLang || undefined,
          target_language: targetLang || undefined,
        });
      }
      setMessage("Settings saved.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page">
      <h1>Settings</h1>

      <div className="form-group">
        <label>Active Deck</label>
        <select
          value={selectedDeckId}
          onChange={(e) => onDeckChange(e.target.value)}
        >
          <option value="">Select a deck...</option>
          {decks.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </div>

      {decks.length === 0 && (
        <p style={{ color: "#e65100", marginBottom: "16px" }}>
          No decks available. Please open Anki on your Mac to perform the
          initial sync.
        </p>
      )}

      <div className="form-group">
        <label>Source Language (language of text you photograph)</label>
        <input
          type="text"
          value={sourceLang}
          onChange={(e) => setSourceLang(e.target.value)}
          placeholder="e.g., German, French, Japanese"
        />
      </div>

      <div className="form-group">
        <label>Target Language (language of translations)</label>
        <input
          type="text"
          value={targetLang}
          onChange={(e) => setTargetLang(e.target.value)}
          placeholder="e.g., English, Spanish"
        />
      </div>

      <div className="form-group">
        <label>Your Native Language (for additional translations)</label>
        <input
          type="text"
          value={nativeLanguage}
          onChange={(e) => setNativeLanguage(e.target.value)}
          placeholder="e.g., English"
        />
      </div>

      {message && (
        <p
          style={{
            marginBottom: "12px",
            color: message.includes("fail") ? "#d32f2f" : "#2e7d32",
          }}
        >
          {message}
        </p>
      )}

      <button
        className="btn btn-primary"
        onClick={handleSave}
        disabled={saving}
      >
        {saving ? "Saving..." : "Save Settings"}
      </button>
    </div>
  );
}
