import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-emerald-600/20 text-emerald-400 border-emerald-500/30",
        secondary:
          "border-transparent bg-slate-800 text-slate-300",
        destructive:
          "border-transparent bg-red-600/20 text-red-400 border-red-500/30",
        outline: "border-slate-700 text-slate-300",
        win: "border-emerald-500/30 bg-emerald-500/20 text-emerald-400",
        draw: "border-amber-500/30 bg-amber-500/20 text-amber-400",
        loss: "border-red-500/30 bg-red-500/20 text-red-400",
        live: "border-red-500/30 bg-red-500/20 text-red-400 animate-pulse",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
