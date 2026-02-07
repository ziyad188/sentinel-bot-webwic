import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ShieldCheck, CheckCircle2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { AuthSession } from "@/lib/auth";

type LoginProps = {
  onLogin: (session: AuthSession, remember: boolean) => void;
};

const Login = ({ onLogin }: LoginProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();
  const state = location.state as { from?: { pathname?: string } } | null;
  const from = state?.from?.pathname ?? "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isDisabled = !email || password.length < 8 || isSubmitting;

  type LoginResponse = {
    user_id: string;
    email: string;
    session?: {
      access_token: string;
      refresh_token: string;
      expires_in: number;
      token_type: string;
    };
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isDisabled) {
      return;
    }

    try {
      setIsSubmitting(true);
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        let message = "Unable to sign you in.";
        try {
          const data = await response.json();
          if (typeof data?.detail === "string") {
            message = data.detail;
          } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
            message = data.detail[0].msg;
          }
        } catch (error) {
          // Ignore JSON parsing errors for non-JSON responses.
        }

        toast({
          variant: "destructive",
          title: "Login failed",
          description: message,
        });
        return;
      }

      let data: LoginResponse | null = null;
      try {
        data = (await response.json()) as LoginResponse;
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Unexpected response",
          description: "We could not read the login response. Try again.",
        });
        return;
      }

      if (!data?.session) {
        toast({
          variant: "destructive",
          title: "Missing session",
          description: "No session was returned by the server.",
        });
        return;
      }

      const session: AuthSession = {
        userId: data.user_id,
        email: data.email,
        accessToken: data.session.access_token,
        refreshToken: data.session.refresh_token,
        expiresIn: data.session.expires_in,
        tokenType: data.session.token_type,
        expiresAt: Date.now() + data.session.expires_in * 1000,
      };

      onLogin(session, remember);
      navigate(from, { replace: true });
    } catch (error) {
      toast({
        variant: "destructive",
        title: "Network error",
        description: "We couldn't reach the server. Try again in a moment.",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-24 right-[-6%] h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute bottom-[-18%] left-[-10%] h-96 w-96 rounded-full bg-accent/60 blur-3xl" />
      </div>

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col items-center justify-center gap-10 px-6 py-12 lg:flex-row lg:justify-between">
        <div className="w-full max-w-xl space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs font-semibold text-muted-foreground shadow-sm">
            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
            Secure access
          </div>

          <div className="space-y-3">
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              Welcome back to SentinelBot
            </h1>
            <p className="text-base text-muted-foreground">
              Monitor automated signup journeys, capture evidence, and escalate issues before they reach customers.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              {
                title: "Vision-driven runs",
                body: "Agent-powered flows with instant friction detection.",
              },
              {
                title: "Issue evidence",
                body: "Screens, logs, and timelines in one shared trail.",
              },
              {
                title: "Continuous alerts",
                body: "P0-P3 escalation with owners and status.",
              },
              {
                title: "Team visibility",
                body: "Shareable dashboards for engineering and growth.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-xl border border-border/70 bg-card/70 p-4 shadow-sm"
              >
                <div className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 text-primary" />
                  <div>
                    <p className="text-sm font-semibold text-foreground">{item.title}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{item.body}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            Trusted by product, QA, and growth teams shipping weekly.
          </div>
        </div>

        <Card className="w-full max-w-md border-border/70 shadow-lg">
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>Use your SentinelBot account to continue.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">Password</Label>
                  <button type="button" className="text-xs text-primary hover:text-primary/90">
                    Forgot password?
                  </button>
                </div>
                <Input
                  id="password"
                  type="password"
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  minLength={8}
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="remember"
                    checked={remember}
                    onCheckedChange={(checked) => setRemember(checked === true)}
                  />
                  <Label htmlFor="remember" className="text-sm font-normal text-muted-foreground">
                    Remember me
                  </Label>
                </div>
                <span className="text-xs text-muted-foreground">SAML ready</span>
              </div>
              <Button type="submit" className="w-full" disabled={isDisabled}>
                {isSubmitting ? "Signing in..." : "Sign in"}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col items-start gap-2 text-xs text-muted-foreground">
            <div className="w-full rounded-lg border border-border/70 bg-muted/40 p-3 text-xs">
              <p className="font-semibold text-foreground">Demo account</p>
              <p className="mt-1">Email: <span className="font-mono">rihan@webwic.com</span></p>
              <p>Password: <span className="font-mono">rihan@123</span></p>
            </div>
            <span>
              New here?{" "}
              <Link to="/signup" className="text-primary hover:text-primary/90">
                Create an account
              </Link>
            </span>
            <span>Need access? Ask your workspace admin to invite you.</span>
            <span>By continuing, you agree to the SentinelBot security policy.</span>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default Login;
