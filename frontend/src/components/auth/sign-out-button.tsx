import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

/** Server-renderable — plain form POST, no client JS needed since there's
 * no Radix asChild wrapping here (unlike the navbar's dropdown item). */
export function SignOutButton() {
  return (
    <form action="/auth/signout" method="post">
      <Button type="submit" variant="outline" className="text-loss hover:text-loss">
        <LogOut className="h-4 w-4" />
        Sign out
      </Button>
    </form>
  );
}
