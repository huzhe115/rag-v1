import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import UploadPage from "./pages/Upload";
import ChatPage from "./pages/Chat";

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <nav className="topnav">
          <NavLink to="/" end className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            文档管理
          </NavLink>
          <NavLink to="/chat" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
            知识库问答
          </NavLink>
        </nav>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
