// Byline: Claude Code · Sonnet (agent) · 2026-07-19
"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import type { FileRejection } from "react-dropzone";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dropzone } from "./dropzone";
import { UploadProgress, type UploadItem } from "./upload-progress";
import { UploadResult } from "./upload-result";
import { uploadFile, ApiError } from "@/lib/api-client";
import { humanizeBytes } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { UploadResponse } from "@/lib/shared/types";

export function UploadForm() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<UploadResponse[]>([]);
  const { triggerRefresh } = useRefresh();

  const handleFilesRejected = useCallback((rejections: FileRejection[]) => {
    for (const rejection of rejections) {
      const name = rejection.file.name;
      const errors = rejection.errors.map((e) => {
        if (e.code === "file-too-large") {
          return `exceeds 100MB limit (${humanizeBytes(rejection.file.size)})`;
        }
        return e.message;
      });
      toast.error(`${name}: ${errors.join(", ")}`);
    }
  }, []);

  const handleFilesSelected = useCallback(
    (files: File[]) => {
      const newItems: UploadItem[] = files.map((file) => ({
        id: `${file.name}-${Date.now()}-${Math.random()}`,
        file,
        progress: 0,
        status: "uploading" as const,
      }));
      setItems((prev) => [...prev, ...newItems]);
      setUploading(true);

      const uploadQueue = async () => {
        let anySuccess = false;
        for (const item of newItems) {
          try {
            const result = await uploadFile(item.file, (percent) => {
              setItems((prev) =>
                prev.map((i) => (i.id === item.id ? { ...i, progress: percent } : i)),
              );
            });

            setItems((prev) =>
              prev.map((i) =>
                i.id === item.id ? { ...i, status: "complete", progress: 100 } : i,
              ),
            );
            setResults((prev) => [...prev, result]);
            if (result.duplicate) {
              toast.warning(`${item.file.name} is already staged`);
            } else {
              toast.success(`${item.file.name} staged`);
            }
            anySuccess = true;
          } catch (err) {
            const message = err instanceof ApiError ? err.message : "Upload failed";
            setItems((prev) =>
              prev.map((i) =>
                i.id === item.id ? { ...i, status: "error", error: message } : i,
              ),
            );
            toast.error(`Failed to upload ${item.file.name}: ${message}`);
          }
        }
        setUploading(false);
        if (anySuccess) triggerRefresh();
      };

      uploadQueue().catch(console.error);
    },
    [triggerRefresh],
  );

  const clearCompleted = useCallback(() => {
    setItems((prev) => prev.filter((i) => i.status === "uploading"));
    setResults([]);
  }, []);

  const hasCompleted = items.some(
    (i) => i.status === "complete" || i.status === "error",
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Dropzone
          onFilesSelected={handleFilesSelected}
          onFilesRejected={handleFilesRejected}
          disabled={uploading}
        />
        <UploadProgress items={items} />
        {results.length > 0 && (
          <div className="space-y-2">
            {results.map((r, i) => (
              <UploadResult key={`${r.id}-${i}`} result={r} />
            ))}
          </div>
        )}
        {hasCompleted && !uploading && (
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={clearCompleted}>
              Clear completed
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
