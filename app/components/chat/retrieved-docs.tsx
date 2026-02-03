import { useState } from "react";
import { ChevronDown, ChevronUp, FileText, ExternalLink } from "lucide-react";
import { Button } from "~/components/ui/button";
import { Badge } from "~/components/ui/badge";
import { cn } from "~/lib/utils";
import type { RetrievedDoc } from "./chat-messages";

interface RetrievedDocsProps {
  docs: RetrievedDoc[];
}

export function RetrievedDocs({ docs }: RetrievedDocsProps) {
  const [expanded, setExpanded] = useState(false);

  if (docs.length === 0) return null;

  return (
    <div className="w-full">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setExpanded(!expanded)}
        className="gap-1.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <FileText className="h-3.5 w-3.5" />
        참고 문서 {docs.length}건
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5" />
        )}
      </Button>

      <div
        className={cn(
          "overflow-hidden transition-all duration-300",
          expanded ? "max-h-[2000px] opacity-100 mt-2" : "max-h-0 opacity-0"
        )}
      >
        <div className="space-y-2">
          {docs.map((doc, i) => (
            <div
              key={i}
              className="rounded-lg border border-border bg-card p-3 text-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <h4 className="font-medium text-card-foreground leading-tight">
                  {doc.index != null ? `[${doc.index}] ` : ""}
                  {doc.title}
                </h4>
                <div className="flex shrink-0 gap-1">
                  {doc.rrf_score != null && (
                    <Badge variant="secondary" className="text-[10px]">
                      RRF {doc.rrf_score.toFixed(3)}
                    </Badge>
                  )}
                  {doc.sim_score != null && (
                    <Badge variant="secondary" className="text-[10px]">
                      SIM {doc.sim_score.toFixed(3)}
                    </Badge>
                  )}
                </div>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground line-clamp-3">
                {doc.text}
              </p>
              {doc.link && (
                <a
                  href={doc.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <ExternalLink className="h-3 w-3" />
                  원문 보기
                </a>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
