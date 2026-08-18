import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

export interface UserProfile {
  id: string;
  name: string;
  email?: string;
  institution?: string;
  bio?: string;
  avatarUrl?: string;
  createdAt: string;
  updatedAt: string;
}

interface ProfileContextType {
  profile: UserProfile | null;
  updateProfile: (profile: Partial<UserProfile>) => void;
  clearProfile: () => void;
  isLoading: boolean;
}

const ProfileContext = createContext<ProfileContextType | undefined>(undefined);

export const useProfile = () => {
  const context = useContext(ProfileContext);
  if (context === undefined) {
    throw new Error('useProfile must be used within a ProfileProvider');
  }
  return context;
};

interface ProfileProviderProps {
  children: ReactNode;
}

export const ProfileProvider: React.FC<ProfileProviderProps> = ({ children }) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const PROFILE_STORAGE_KEY = 'dina_user_profile';

  // Load profile from localStorage on mount
  useEffect(() => {
    const loadProfile = () => {
      try {
        const storedProfile = localStorage.getItem(PROFILE_STORAGE_KEY);
        if (storedProfile) {
          const parsedProfile = JSON.parse(storedProfile);
          setProfile(parsedProfile);
        }
      } catch (error) {
        console.error('Error loading profile from localStorage:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadProfile();
  }, []);

  const updateProfile = (profileUpdate: Partial<UserProfile>) => {
    const now = new Date().toISOString();

    const newProfile: UserProfile = profile
      ? {
          ...profile,
          ...profileUpdate,
          updatedAt: now
        }
      : {
          id: crypto.randomUUID(),
          name: profileUpdate.name || '',
          email: profileUpdate.email,
          institution: profileUpdate.institution,
          bio: profileUpdate.bio,
          avatarUrl: profileUpdate.avatarUrl,
          createdAt: now,
          updatedAt: now
        };

    setProfile(newProfile);

    // Save to localStorage
    try {
      localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(newProfile));
    } catch (error) {
      console.error('Error saving profile to localStorage:', error);
    }
  };

  const clearProfile = () => {
    setProfile(null);
    try {
      localStorage.removeItem(PROFILE_STORAGE_KEY);
    } catch (error) {
      console.error('Error clearing profile from localStorage:', error);
    }
  };

  const value: ProfileContextType = {
    profile,
    updateProfile,
    clearProfile,
    isLoading
  };

  return (
    <ProfileContext.Provider value={value}>
      {children}
    </ProfileContext.Provider>
  );
};