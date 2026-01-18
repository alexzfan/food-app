import { jest, describe, it, expect, beforeEach } from "@jest/globals";
import { Request, Response, NextFunction } from "express";
import {
  authMiddleware,
  verifiedAuthMiddleware,
  optionalAuthMiddleware,
} from "../../middleware/auth.js";

// Mock @supabase/supabase-js
jest.mock("@supabase/supabase-js", () => ({
  createClient: jest.fn(),
}));

import { createClient } from "@supabase/supabase-js";

const mockCreateClient = createClient as jest.MockedFunction<
  typeof createClient
>;

describe("Auth Middleware", () => {
  let mockReq: Partial<Request>;
  let mockRes: Partial<Response>;
  let mockNext: NextFunction;
  let mockSupabase: any;

  beforeEach(() => {
    mockReq = {
      headers: {},
    };
    mockRes = {
      status: jest.fn().mockReturnThis() as any,
      json: jest.fn().mockReturnThis() as any,
    };
    mockNext = jest.fn();

    mockSupabase = {
      auth: {
        getUser: jest.fn(),
      },
    };

    mockCreateClient.mockReturnValue(mockSupabase as any);
  });

  describe("authMiddleware", () => {
    it("should return 401 when no authorization header", async () => {
      await authMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: "Missing or invalid authorization header",
      });
      expect(mockNext).not.toHaveBeenCalled();
    });

    it("should return 401 when authorization header is malformed", async () => {
      mockReq.headers = { authorization: "InvalidFormat token123" };

      await authMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: "Missing or invalid authorization header",
      });
    });

    it("should return 401 when token is invalid", async () => {
      mockReq.headers = { authorization: "Bearer invalid-token" };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: null },
        error: { message: "Invalid token" },
      });

      await authMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: "Invalid or expired token",
      });
    });

    it("should attach user and call next when token is valid", async () => {
      mockReq.headers = { authorization: "Bearer valid-token" };
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        email_confirmed_at: "2024-01-01T00:00:00Z",
      };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: mockUser },
        error: null,
      });

      await authMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user).toEqual({
        id: "user-123",
        email: "test@example.com",
        emailVerified: true,
      });
      expect(mockReq.supabase).toBeDefined();
      expect(mockNext).toHaveBeenCalled();
    });

    it("should set emailVerified to false when email not confirmed", async () => {
      mockReq.headers = { authorization: "Bearer valid-token" };
      const mockUser = {
        id: "user-456",
        email: "unverified@example.com",
        email_confirmed_at: null,
      };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: mockUser },
        error: null,
      });

      await authMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user?.emailVerified).toBe(false);
      expect(mockNext).toHaveBeenCalled();
    });
  });

  describe("verifiedAuthMiddleware", () => {
    it("should return 401 when no authorization header", async () => {
      await verifiedAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockRes.status).toHaveBeenCalledWith(401);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: "Missing or invalid authorization header",
      });
    });

    it("should return 403 when email not verified", async () => {
      mockReq.headers = { authorization: "Bearer valid-token" };
      const mockUser = {
        id: "user-789",
        email: "unverified@example.com",
        email_confirmed_at: null,
      };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: mockUser },
        error: null,
      });

      await verifiedAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockRes.status).toHaveBeenCalledWith(403);
      expect(mockRes.json).toHaveBeenCalledWith({
        error: "Email not verified",
        code: "EMAIL_NOT_VERIFIED",
        email: "unverified@example.com",
      });
      expect(mockNext).not.toHaveBeenCalled();
    });

    it("should call next when email is verified", async () => {
      mockReq.headers = { authorization: "Bearer valid-token" };
      const mockUser = {
        id: "user-verified",
        email: "verified@example.com",
        email_confirmed_at: "2024-01-01T00:00:00Z",
      };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: mockUser },
        error: null,
      });

      await verifiedAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user?.emailVerified).toBe(true);
      expect(mockNext).toHaveBeenCalled();
    });
  });

  describe("optionalAuthMiddleware", () => {
    it("should call next without user when no authorization header", async () => {
      await optionalAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user).toBeUndefined();
      expect(mockNext).toHaveBeenCalled();
    });

    it("should call next without user when token is invalid", async () => {
      mockReq.headers = { authorization: "Bearer invalid-token" };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: null },
        error: { message: "Invalid token" },
      });

      await optionalAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user).toBeUndefined();
      expect(mockNext).toHaveBeenCalled();
    });

    it("should attach user when token is valid", async () => {
      mockReq.headers = { authorization: "Bearer valid-token" };
      const mockUser = {
        id: "optional-user",
        email: "optional@example.com",
        email_confirmed_at: "2024-01-01T00:00:00Z",
      };
      mockSupabase.auth.getUser.mockResolvedValue({
        data: { user: mockUser },
        error: null,
      });

      await optionalAuthMiddleware(
        mockReq as Request,
        mockRes as Response,
        mockNext
      );

      expect(mockReq.user).toEqual({
        id: "optional-user",
        email: "optional@example.com",
        emailVerified: true,
      });
      expect(mockNext).toHaveBeenCalled();
    });
  });
});
