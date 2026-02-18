import { useEffect, useState } from "react";
import { api } from "../api/client";

interface CardItem {
  id: string;
  fields: Record<string, string>;
  status: string;
  source_word: string | null;
  created_at: string;
}

interface Props {
  deckId: string;
}

export default function CardsPage({ deckId }: Props) {
  const [cards, setCards] = useState<CardItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCards();
  }, [deckId]);

  const loadCards = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (deckId) params.deck_id = deckId;
      const result = await api.listCards(params);
      setCards(result);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const pendingCount = cards.filter((c) => c.status === "pending_sync").length;

  if (loading) {
    return (
      <div className="page">
        <h1>Cards</h1>
        <div className="loading">Loading cards...</div>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Cards</h1>

      {pendingCount > 0 && (
        <p style={{ marginBottom: "12px", color: "#1565c0" }}>
          {pendingCount} card{pendingCount !== 1 ? "s" : ""} pending sync
        </p>
      )}

      {cards.length === 0 ? (
        <p style={{ color: "#666" }}>No cards yet. Take a photo to get started.</p>
      ) : (
        cards.map((card) => (
          <div key={card.id} className="card-preview" style={{ marginBottom: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
              <strong>{card.source_word || "Card"}</strong>
              <span className={`status-badge ${card.status}`}>{card.status}</span>
            </div>
            {Object.entries(card.fields)
              .slice(0, 3)
              .map(([name, value]) => (
                <div className="field" key={name}>
                  <div className="field-name">{name}</div>
                  <div className="field-value">{value}</div>
                </div>
              ))}
          </div>
        ))
      )}
    </div>
  );
}
