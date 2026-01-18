import { describe, it, expect } from "@jest/globals";
import request from "supertest";
import { app } from "../../app.js";

describe("App", () => {
  describe("GET /health", () => {
    it("should return health status", async () => {
      const response = await request(app).get("/health");

      expect(response.status).toBe(200);
      expect(response.body.status).toBe("ok");
      expect(response.body.timestamp).toBeDefined();
      expect(new Date(response.body.timestamp)).toBeInstanceOf(Date);
    });
  });

  describe("Error handling", () => {
    it("should return 404 for unknown routes", async () => {
      const response = await request(app).get("/api/nonexistent");

      expect(response.status).toBe(404);
    });
  });
});
