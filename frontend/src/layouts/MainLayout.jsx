/**
 * Japan OCR Tool - Main Layout
 *
 * Shell layout rendered for all authenticated routes. Composes the persistent
 * Header with a full-height scrollable content area via React Router's Outlet.
 *
 * Key Features:
 * - Shell: Provides consistent chrome (header + main) for every protected page
 * - Responsive Padding: Scales horizontal padding across sm → 2xl breakpoints
 *
 * Dependencies: React Router (Outlet), Header component
 * Author: SHIRIN MIRZI M K
 */
import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/Header';

/**
 * Renders the full-page shell consisting of the Header and a content Outlet.
 *
 * @returns {JSX.Element} Flex-column page wrapper with Header and main content
 */
export default function MainLayout() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      <main className="flex-1 w-full px-4 py-4 sm:px-6 sm:py-5 md:px-8 md:py-6 lg:px-12 xl:px-16 2xl:px-24">
        <Outlet />
      </main>
    </div>
  );
}
