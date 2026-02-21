import { Routes, Route, Navigate, Link, useLocation } from "react-router-dom";
import { getToken, setToken } from "./api/client";
import LoginPage from "./pages/LoginPage";
import CameraPage from "./pages/CameraPage";
import WordSelectPage from "./pages/WordSelectPage";
import TranslatePage from "./pages/TranslatePage";
import CardsPage from "./pages/CardsPage";
import ConfigPage from "./pages/ConfigPage";
import { useState } from "react";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function Header() {
  const location = useLocation();
  const isActive = (path: string) =>
    location.pathname === path ? "active" : "";

  return (
    <header className="header">
      <h1>Anki Translator</h1>
      <nav>
        <Link to="/" className={isActive("/")}>
          Camera
        </Link>
        <Link to="/cards" className={isActive("/cards")}>
          Cards
        </Link>
        <Link to="/config" className={isActive("/config")}>
          Settings
        </Link>
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setToken(null);
            window.location.href = "/login";
          }}
        >
          Logout
        </a>
      </nav>
    </header>
  );
}

export default function App() {
  // Shared state for the photo→word→translate flow
  const [ocrWords, setOcrWords] = useState<string[]>([]);
  const [selectedWord, setSelectedWord] = useState<string>("");
  const [selectedDeckId, _setSelectedDeckId] = useState<string>(
    localStorage.getItem("selectedDeckId") || "",
  );

  const setSelectedDeckId = (id: string) => {
    _setSelectedDeckId(id);
    localStorage.setItem("selectedDeckId", id);
  };

  return (
    <div className="app">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <>
                <Header />
                <Routes>
                  <Route
                    path="/"
                    element={<CameraPage onWordsExtracted={setOcrWords} />}
                  />
                  <Route
                    path="/words"
                    element={
                      <WordSelectPage
                        words={ocrWords}
                        onWordSelected={(w) => setSelectedWord(w)}
                        deckId={selectedDeckId}
                      />
                    }
                  />
                  <Route
                    path="/translate"
                    element={
                      <TranslatePage
                        word={selectedWord}
                        deckId={selectedDeckId}
                      />
                    }
                  />
                  <Route
                    path="/cards"
                    element={<CardsPage deckId={selectedDeckId} />}
                  />
                  <Route
                    path="/config"
                    element={
                      <ConfigPage
                        selectedDeckId={selectedDeckId}
                        onDeckChange={setSelectedDeckId}
                      />
                    }
                  />
                </Routes>
              </>
            </ProtectedRoute>
          }
        />
      </Routes>
    </div>
  );
}
