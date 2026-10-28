import * as React from "react"

import { cn } from "@/lib/utils"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full rounded-md border border-input bg-card px-3.5 py-3 text-base transition-[border-color,box-shadow] duration-150 outline-none placeholder:text-muted-foreground hover:border-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-brand-subtle disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-error aria-invalid:ring-3 aria-invalid:ring-error-subtle",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
