'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';

export function Navigation() {
  const pathname = usePathname();
  const { user } = useAuth();

  const links = [
    { href: '/', label: 'Matches', public: true },
    { href: '/dashboard', label: 'Dashboard', requireAuth: true },
    { href: '/matches/create', label: 'Create Match', requireRole: 'coach' },
  ];

  const visibleLinks = links.filter((link) => {
    if (link.public) return true;
    if (link.requireAuth && !user) return false;
    if (link.requireRole && user?.role !== link.requireRole && user?.role !== 'admin') {
      return false;
    }
    return true;
  });

  return (
    <nav className="flex items-center gap-1 md:gap-2">
      {visibleLinks.map((link) => {
        const isActive = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              'px-3 py-2 rounded-md text-sm font-medium transition-colors',
              isActive
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-700 hover:bg-gray-100'
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
