import { type RouteConfig, index, route, layout } from "@react-router/dev/routes";

export default [
  // Root index redirects to chat
  index("routes/home.tsx"),

  // Auth routes
  route("auth/login", "routes/auth/login.tsx"),
  route("auth/signup", "routes/auth/signup.tsx"),
  route("auth/forgot-password", "routes/auth/forgot-password.tsx"),
  route("auth/update-password", "routes/auth/update-password.tsx"),
  route("auth/confirm", "routes/auth/confirm.tsx"),

  // Chat routes (nested under layout)
  layout("routes/chat.tsx", [
    route("chat", "routes/chat._index.tsx"),
    route("chat/:conversationId", "routes/chat.$conversationId.tsx"),
  ]),
] satisfies RouteConfig;
