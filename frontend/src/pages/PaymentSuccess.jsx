import { useEffect, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { paymentStatus } from "../lib/api";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

export default function PaymentSuccess() {
  const [params] = useSearchParams();
  const sessionId = params.get("session_id");
  const [state, setState] = useState({ loading: true, status: null, data: null });

  useEffect(() => {
    if (!sessionId) return;
    let tries = 0;
    let alive = true;
    const poll = async () => {
      tries++;
      try {
        const data = await paymentStatus(sessionId);
        if (!alive) return;
        if (data.payment_status === "paid") {
          setState({ loading: false, status: "paid", data });
          return;
        }
        if (data.payment_status === "expired" || data.payment_status === "failed") {
          setState({ loading: false, status: data.payment_status, data });
          return;
        }
        if (tries < 30) {
          setTimeout(poll, 2000);
        } else {
          setState({ loading: false, status: "timeout", data });
        }
      } catch {
        if (tries < 20) setTimeout(poll, 2500);
        else setState({ loading: false, status: "error", data: null });
      }
    };
    poll();
    return () => { alive = false; };
  }, [sessionId]);

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="border border-[color:var(--fb-border)] bg-[color:var(--fb-surface)] p-8 md:p-12 max-w-lg w-full">
        {state.loading && (
          <div className="text-center" data-testid="payment-loading">
            <Loader2 className="mx-auto mb-4 animate-spin text-[color:var(--fb-cyan)]" size={40} />
            <h1 className="font-display text-3xl text-white">Confirming your bid…</h1>
            <p className="font-mono text-sm text-[color:var(--fb-text-2)] mt-2">Talking to Stripe. Hang tight.</p>
          </div>
        )}
        {!state.loading && state.status === "paid" && (
          <div className="text-center" data-testid="payment-success">
            <CheckCircle2 className="mx-auto mb-4 text-[color:var(--fb-green)]" size={48} />
            <h1 className="font-display text-4xl font-black text-white">You're on the board.</h1>
            <p className="font-mono text-sm text-[color:var(--fb-text-2)] mt-3">
              Bid confirmed: <span className="text-[color:var(--fb-green)]">${Number(state.data?.amount || 0).toFixed(2)}</span>
              {state.data?.purpose === "outbid" ? " · Outbid successful" : ""}
            </p>
            <Link to="/" className="fb-btn-primary inline-block mt-6" data-testid="back-to-board">
              See the board
            </Link>
          </div>
        )}
        {!state.loading && state.status !== "paid" && (
          <div className="text-center" data-testid="payment-failed">
            <XCircle className="mx-auto mb-4 text-[color:var(--fb-pink)]" size={48} />
            <h1 className="font-display text-3xl text-white">Payment not confirmed</h1>
            <p className="font-mono text-sm text-[color:var(--fb-text-2)] mt-2">
              Status: {state.status || "unknown"}. Try again from the board.
            </p>
            <Link to="/" className="fb-btn-ghost inline-block mt-6">Back to board</Link>
          </div>
        )}
      </div>
    </div>
  );
}
