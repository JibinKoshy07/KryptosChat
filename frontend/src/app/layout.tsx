import "@/app/globals.css";

export const metadata = {
  title: "Krypte",
  description: "Private, self-hosted, encrypted real-time chat.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}