import { redirect } from "next/navigation";
import { cookies } from "next/headers";

export default function Root() {
  const token = cookies().get("futuro_token");
  if (token?.value) redirect("/chat");
  redirect("/login");
}
