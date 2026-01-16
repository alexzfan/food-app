import { extractRecipeFromTranscript } from "../../services/claude";
import { mockRecipeSummary, mockTranscript } from "../mocks";

// Mock the Anthropic SDK
jest.mock("@anthropic-ai/sdk", () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      messages: {
        create: jest.fn(),
      },
    })),
  };
});

import Anthropic from "@anthropic-ai/sdk";

describe("Claude Service", () => {
  let mockCreate: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockCreate = (new Anthropic() as any).messages.create;
  });

  describe("extractRecipeFromTranscript", () => {
    it("should extract recipe from transcript successfully", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "text",
            text: JSON.stringify(mockRecipeSummary),
          },
        ],
      });

      const result = await extractRecipeFromTranscript(
        mockTranscript,
        "Easy Garlic Parmesan Pasta"
      );

      expect(mockCreate).toHaveBeenCalledTimes(1);
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          model: "claude-sonnet-4-20250514",
          max_tokens: 4096,
        })
      );

      expect(result).toEqual(mockRecipeSummary);
    });

    it("should handle JSON wrapped in markdown code blocks", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "text",
            text: "```json\n" + JSON.stringify(mockRecipeSummary) + "\n```",
          },
        ],
      });

      const result = await extractRecipeFromTranscript(
        mockTranscript,
        "Test Recipe"
      );

      expect(result).toEqual(mockRecipeSummary);
    });

    it("should handle code blocks without json specifier", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "text",
            text: "```\n" + JSON.stringify(mockRecipeSummary) + "\n```",
          },
        ],
      });

      const result = await extractRecipeFromTranscript(
        mockTranscript,
        "Test Recipe"
      );

      expect(result).toEqual(mockRecipeSummary);
    });

    it("should throw error on invalid JSON response", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "text",
            text: "This is not valid JSON at all",
          },
        ],
      });

      await expect(
        extractRecipeFromTranscript(mockTranscript, "Test Recipe")
      ).rejects.toThrow("Failed to parse recipe from Claude response");
    });

    it("should throw error on unexpected response type", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "image",
            source: {},
          },
        ],
      });

      await expect(
        extractRecipeFromTranscript(mockTranscript, "Test Recipe")
      ).rejects.toThrow("Unexpected response type from Claude");
    });

    it("should include video title in the prompt", async () => {
      mockCreate.mockResolvedValueOnce({
        content: [
          {
            type: "text",
            text: JSON.stringify(mockRecipeSummary),
          },
        ],
      });

      await extractRecipeFromTranscript(mockTranscript, "My Special Recipe");

      const callArgs = mockCreate.mock.calls[0][0];
      expect(callArgs.messages[0].content).toContain("My Special Recipe");
    });
  });
});
