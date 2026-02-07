import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck, CheckCircle2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { AuthSession } from "@/lib/auth";

type SignupProps = {
  onSignup: (session: AuthSession) => void;
};

type SignupResponse = {
  user_id: string;
  email: string;
  confirmation_required: boolean;
  session?: {
    access_token: string;
    refresh_token: string;
    expires_in: number;
    token_type: string;
  };
};

const Signup = ({ onSignup }: SignupProps) => {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isDisabled = !email || password.length < 8 || isSubmitting;

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isDisabled) {
      return;
    }

    const payload: {
      email: string;
      password: string;
      full_name?: string;
    } = { email, password };

    if (fullName.trim()) {
      payload.full_name = fullName.trim();
    }

    try {
      setIsSubmitting(true);
      const response = await fetch("/auth/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = "Unable to create your account.";
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
          title: "Signup failed",
          description: message,
        });
        return;
      }

      let data: SignupResponse | null = null;
      try {
        data = (await response.json()) as SignupResponse;
      } catch (error) {
        toast({
          variant: "destructive",
          title: "Unexpected response",
          description: "We could not read the signup response. Try again.",
        });
        return;
      }

      if (!data?.session || data.confirmation_required) {
        toast({
          title: "Confirm your email",
          description: "Check your inbox to finish setting up your account.",
        });
        navigate("/login", { replace: true });
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

      onSignup(session);
      toast({
        title: "Account created",
        description: "You're signed in and ready to go.",
      });
      navigate("/dashboard", { replace: true });
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
            Create access
          </div>

          <div className="space-y-3">
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
              Build your SentinelBot workspace
            </h1>
            <p className="text-base text-muted-foreground">
              Spin up a monitoring workspace in minutes. Invite your team and keep signups healthy.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {[
              {
                title: "Guided onboarding",
                body: "Set your first run with a ready-made template.",
              },
              {
                title: "Fast setup",
                body: "Bring staging and production flows together.",
              },
              {
                title: "Agent clarity",
                body: "Every run ships with clear ownership and steps.",
              },
              {
                title: "Shareable reports",
                body: "Weekly snapshots for your leadership team.",
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
            Secure by default with role-based access controls.
          </div>
        </div>

        <Card className="w-full max-w-md border-border/70 shadow-lg">
          <CardHeader>
            <CardTitle>Create account</CardTitle>
            <CardDescription>Use your work email to get started.</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="full-name">Full name (optional)</Label>
                <Input
                  id="full-name"
                  type="text"
                  placeholder="Alex Morgan"
                  autoComplete="name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                />
              </div>
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
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="Create a password"
                  autoComplete="new-password"
                  minLength={8}
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">Must be 8-128 characters.</p>
              </div>
              <Button type="submit" className="w-full" disabled={isDisabled}>
                {isSubmitting ? "Creating account..." : "Create account"}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col items-start gap-2 text-xs text-muted-foreground">
            <span>
              Already have an account?{" "}
              <Link to="/login" className="text-primary hover:text-primary/90">
                Sign in
              </Link>
            </span>
            <span>By creating an account, you agree to the SentinelBot terms.</span>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
};

export default Signup;
