import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control text-body font-medium transition-colors duration-quick ease-shutter disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        // The run action — the only gradient surface in the product (UI_SCHEMA §1.4).
        run: "bg-[image:var(--ks-accent-gradient)] text-white shadow-[0_6px_20px_-6px_rgba(99,102,241,0.7)] hover:brightness-110",
        default: "bg-ks-lift text-ks-ink hover:bg-[#212740]",
        outline: "border border-ks-line-strong bg-transparent text-ks-ink hover:bg-ks-lift",
        ghost: "text-ks-ink-2 hover:bg-ks-lift hover:text-ks-ink",
        destructive: "bg-ks-deny text-white hover:brightness-110",
        link: "text-ks-ink underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-3.5",
        sm: "h-8 px-2.5 text-meta",
        lg: "h-10 px-5",
        icon: "h-9 w-9",
        "icon-sm": "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
