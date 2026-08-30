import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "next-themes";
import { Toaster } from "@/components/ui/sonner";
import Board from "@/pages/Board";
import ProductDetail from "@/pages/ProductDetail";
import ShareLanding from "@/pages/ShareLanding";

export default function App() {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem={false}>
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Board />} />
          <Route path="/product/:id" element={<ProductDetail />} />
          <Route path="/s/:token" element={<ShareLanding />} />
        </Routes>
      </BrowserRouter>
      <Toaster theme="dark" position="top-right" />
    </div>
    </ThemeProvider>
  );
}
