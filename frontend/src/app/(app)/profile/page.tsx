import type { Metadata } from "next";
import { User } from "lucide-react";
import { createClient } from "@/lib/supabase/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Label } from "@/components/ui/label";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { SignOutButton } from "@/components/auth/sign-out-button";
import { PageHeader } from "@/components/layout/page-header";
import { GuestState } from "@/components/auth/guest-state";

export const metadata: Metadata = { title: "Profile" };

export default async function ProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Profile data is per-account (RLS scopes `profiles` to auth.uid() = id), so
  // there is nothing to show a guest — but that is a reason for an honest guest
  // state, not a redirect. Theme preference still works without an account, so
  // it stays available below.
  if (!user) {
    return (
      <div className="max-w-2xl space-y-8">
        <PageHeader
          icon={User}
          title="Profile"
          description="Account details and preferences"
        />
        <GuestState
          icon={User}
          title="You're browsing as a guest"
          description="The whole site — predictions, simulations, the bracket and analytics — works without an account. Sign in if you'd like saved predictions and a personal history."
          redirectTo="/profile"
          showCreateAccount
        />
        <Card>
          <CardHeader>
            <CardTitle>Preferences</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <Label>Theme</Label>
              <ThemeToggle />
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { data: profile } = await supabase
    .from("profiles")
    .select("full_name, avatar_url, role")
    .eq("id", user.id)
    .single();

  const displayName = profile?.full_name || user.email || "Your account";
  const initials = displayName[0]?.toUpperCase() ?? "?";

  return (
    <div className="max-w-2xl space-y-8">
      <PageHeader
        icon={User}
        title="Profile"
        description="Your account details and preferences"
      />

      <Card>
        <CardContent className="flex items-center gap-4 p-6">
          <Avatar className="h-16 w-16">
            {profile?.avatar_url && <AvatarImage src={profile.avatar_url} alt={displayName} />}
            <AvatarFallback className="text-xl">{initials}</AvatarFallback>
          </Avatar>
          <div>
            <p className="text-lg font-semibold text-foreground">{displayName}</p>
            <p className="text-sm text-fg-muted">{user.email}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preferences</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <Label>Theme</Label>
            <ThemeToggle />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-fg-muted">Email</span>
            <span className="text-foreground">{user.email}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-fg-muted">Member since</span>
            <span className="text-foreground">{new Date(user.created_at).toLocaleDateString()}</span>
          </div>
          <Separator />
          <SignOutButton />
        </CardContent>
      </Card>
    </div>
  );
}
