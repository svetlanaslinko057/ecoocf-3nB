import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

const Dialog = DialogPrimitive.Root

const DialogTrigger = DialogPrimitive.Trigger

const DialogPortal = DialogPrimitive.Portal

const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/80  data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props} />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

const DialogContent = React.forwardRef(({ className, children, onPointerDownOutside, onInteractOutside, ...props }, ref) => {
  // Project-wide defense: any portaled popover that lives OUTSIDE the
  // DialogContent React tree (e.g. our custom WhiteDatePicker calendar,
  // WhiteSelect dropdown, or any other element marked with the
  // `data-portal-keep-dialog-open` attribute) must NOT cause Radix to
  // dismiss the dialog. We veto Radix's outside-detection by inspecting
  // the originating DOM target and calling event.preventDefault() if it
  // matches one of our trusted portal markers.
  //
  // Markers honoured:
  //   - [data-whitedatepicker-popover]          → WhiteDatePicker calendar
  //   - [data-portal-keep-dialog-open]          → opt-in marker for any
  //                                                future portaled component
  //
  // Page-level handlers passed via props still run AFTER this default
  // guard, so individual dialogs can extend (but not weaken) the policy.
  const TRUSTED_PORTAL_SELECTOR =
    '[data-whitedatepicker-popover],[data-portal-keep-dialog-open]';

  const guardInteractOutside = (event) => {
    const target = event.target;
    const orig = event.detail && event.detail.originalEvent ? event.detail.originalEvent.target : null;
    const inPop =
      (target && typeof target.closest === 'function' && target.closest(TRUSTED_PORTAL_SELECTOR)) ||
      (orig   && typeof orig.closest   === 'function' && orig.closest(TRUSTED_PORTAL_SELECTOR));
    if (inPop) {
      event.preventDefault();
      return;
    }
    if (typeof onInteractOutside === 'function') onInteractOutside(event);
  };
  const guardPointerDownOutside = (event) => {
    const target = event.target;
    const orig = event.detail && event.detail.originalEvent ? event.detail.originalEvent.target : null;
    const inPop =
      (target && typeof target.closest === 'function' && target.closest(TRUSTED_PORTAL_SELECTOR)) ||
      (orig   && typeof orig.closest   === 'function' && orig.closest(TRUSTED_PORTAL_SELECTOR));
    if (inPop) {
      event.preventDefault();
      return;
    }
    if (typeof onPointerDownOutside === 'function') onPointerDownOutside(event);
  };

  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        ref={ref}
        onInteractOutside={guardInteractOutside}
        onPointerDownOutside={guardPointerDownOutside}
        className={cn(
          "fixed left-[50%] top-[50%] z-50 grid w-[calc(100%-32px)] max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] rounded-2xl max-h-[90vh] overflow-y-auto",
          className
        )}
        {...props}>
        {children}
        <DialogPrimitive.Close
          className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
          <X className="h-4 w-4" />
          <span className="sr-only">Close</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPortal>
  );
})
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({
  className,
  ...props
}) => (
  <div
    className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}
    {...props} />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({
  className,
  ...props
}) => (
  <div
    className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}
    {...props} />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props} />
))
DialogTitle.displayName = DialogPrimitive.Title.displayName

const DialogDescription = React.forwardRef(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-sm text-muted-foreground", className)}
    {...props} />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
