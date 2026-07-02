import Link from "next/link";
import { Trophy, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-8">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-500">
            <Trophy className="h-5 w-5 text-white" />
          </div>
        </div>
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <Mail className="h-8 w-8 text-emerald-400" />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-white mb-3">Check your email</h1>
        <p className="text-slate-400 mb-8">
          We sent a confirmation link to your email address. Click it to activate
          your account and start predicting.
        </p>
        <Button variant="outline" asChild>
          <Link href="/auth/login">Back to sign in</Link>
        </Button>
      </div>
    </div>
  );
}
