import fs from "node:fs/promises";
import path from "node:path";
import type { RivalryData } from "./types";

const DATA_DIR = path.resolve("../backend/data/analyses");

export async function getAllRivalries(): Promise<RivalryData[]> {
  try {
    const entries = await fs.readdir(DATA_DIR, { withFileTypes: true });

    // Filter for directories only
    const rivalryDirs = entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name);

    const rivalries: RivalryData[] = [];

    for (const dirName of rivalryDirs) {
      const analysisPath = path.join(DATA_DIR, dirName, "analysis.json");

      try {
        const content = await fs.readFile(analysisPath, "utf-8");
        const data = JSON.parse(content) as RivalryData;

        if (data.rivalry_exists) {
          rivalries.push(data);
        }
      } catch (err) {
        console.warn(`Failed to read or parse analysis for ${dirName}:`, err);
        // Continue to next directory even if one fails
      }
    }

    return rivalries;
  } catch (error) {
    console.error("Error reading data directory:", error);
    return [];
  }
}
