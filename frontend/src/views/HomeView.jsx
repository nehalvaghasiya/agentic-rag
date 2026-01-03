import { MessageSquare } from "lucide-react";

import { Card, CardContent, CardDescription, CardTitle } from "../components/ui/Card";

export function HomeView({ onStartChat }) {
  return (
    <div className="flex h-full items-center justify-center px-6">
      <div className="w-full max-w-4xl">
        <div className="text-center">
          <div className="text-2xl font-semibold text-text">
            Welcome!
          </div>
          <div className="mt-2 text-sm text-muted">
            What would you like to do today?
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-1">
          <button type="button" onClick={onStartChat} className="text-left">
            <Card className="transition-colors hover:bg-border/20">
              <CardContent className="px-6 py-6">
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-bg text-muted">
                    <MessageSquare size={18} />
                  </div>
                  <div>
                    <CardTitle>Start New Chat</CardTitle>
                    <CardDescription className="mt-1">
                      General chat. Optionally use a knowledge base for citations.
                    </CardDescription>
                  </div>
                </div>
              </CardContent>
            </Card>
          </button>
        </div>
      </div>
    </div>
  );
}
