import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { hitShare } from "../lib/api";
import { Loader2 } from "lucide-react";

export default function ShareLanding() {
  const { token } = useParams();
  const navigate = useNavigate();
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    hitShare(token)
      .then((data) => {
        if (!alive) return;
        navigate(data.redirect || `/product/${data.listing_id}`, { replace: true });
      })
      .catch(() => {
        if (alive) setErr("This share link is invalid or expired.");
      });
    return () => { alive = false; };
  }, [token, navigate]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center">
      {err ? (
        <>
          <p className="font-mono text-sm text-[color:var(--fb-text-2)]">{err}</p>
          <button onClick={() => navigate("/")} className="fb-btn-primary mt-6">Back to board</button>
        </>
      ) : (
        <>
          <Loader2 className="animate-spin text-[color:var(--fb-cyan)]" size={36} />
          <p className="font-mono text-xs text-[color:var(--fb-muted)] mt-4 uppercase tracking-widest">
            Opening listing…
          </p>
        </>
      )}
    </div>
  );
}
