import { Link } from "react-router-dom";
import { XCircle } from "lucide-react";

export default function PaymentCancel() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="border border-[color:var(--fb-border)] bg-[color:var(--fb-surface)] p-8 md:p-12 max-w-lg text-center" data-testid="payment-cancel">
        <XCircle className="mx-auto mb-4 text-[color:var(--fb-pink)]" size={48} />
        <h1 className="font-display text-3xl text-white">Bid cancelled.</h1>
        <p className="font-mono text-sm text-[color:var(--fb-text-2)] mt-2">
          No charge made. The board waits for no one — try again when you're ready.
        </p>
        <Link to="/" className="fb-btn-primary inline-block mt-6" data-testid="cancel-back-btn">Back to board</Link>
      </div>
    </div>
  );
}
