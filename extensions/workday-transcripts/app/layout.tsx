import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Workday Learn - Spaced Repetition Training',
  description:
    'Master Workday concepts through scientifically-backed spaced repetition learning',
  keywords: ['Workday', 'training', 'spaced repetition', 'flashcards', 'HCM', 'learning'],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <div className="min-h-screen bg-background">
          <header className="border-b border-border bg-card">
            <div className="container mx-auto px-4 py-4">
              <nav className="flex items-center justify-between">
                <a href="/" className="flex items-center gap-2">
                  <div className="w-8 h-8 bg-workday-blue rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-sm">W</span>
                  </div>
                  <span className="font-semibold text-lg">Workday Learn</span>
                </a>
                <div className="flex items-center gap-6">
                  <a
                    href="/review"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Review
                  </a>
                  <a
                    href="/transcripts"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Transcripts
                  </a>
                  <a
                    href="/stats"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Statistics
                  </a>
                </div>
              </nav>
            </div>
          </header>
          <main className="container mx-auto px-4 py-8">{children}</main>
          <footer className="border-t border-border bg-card mt-auto">
            <div className="container mx-auto px-4 py-4 text-center text-sm text-muted-foreground">
              <p>Workday Learn - Spaced Repetition for Workday Mastery</p>
              <p className="mt-1">
                Using the SM-2 algorithm for optimal retention
              </p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
