import React from 'react';
import { Outlet } from 'react-router-dom';
import Header from '../components/Header';

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
