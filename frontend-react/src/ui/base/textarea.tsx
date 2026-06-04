import * as React from "react"

import { cn } from "@/services/tech/TailwindS"

interface TextAreaProps extends React.ComponentProps<"textarea"> {
  maxHeight?: number
}

function TextArea({ className, maxHeight = 200, value, ...props }: TextAreaProps) {
  const ref = React.useRef<HTMLTextAreaElement>(null)

  React.useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, maxHeight).toString()}px`
  }, [value, maxHeight])

  return (
    <textarea
      ref={ref}
      data-slot="textarea"
      value={value}
      className={cn(
        "block w-full resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed",
        className
      )}
      {...props}
    />
  )
}

export { TextArea }
