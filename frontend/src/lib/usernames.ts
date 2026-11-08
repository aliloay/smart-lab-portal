/** Usernames (owner 2026-10-20) - same rules as backend/app/core/usernames.py: firstname.lastname,
 *  small letters, a dot between the names. Used to pre-fill and check the forms; the server decides. */
const PATTERN = /^[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)+$/
const TITLES = new Set(['dr', 'eng', 'engr', 'prof', 'mr', 'mrs', 'ms', 'miss', 'sir'])
export const USERNAME_HINT = 'firstname.lastname - small letters, a dot between the names (e.g. ali.abozeid)'

export function suggestUsername(fullName: string): string {
  const parts = fullName.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .split(/[^a-z0-9]+/).filter(p => p && !TITLES.has(p))
  return parts.length < 2 ? (parts[0] ?? '') : `${parts[0]}.${parts[parts.length - 1]}`
}

export const validUsername = (u: string) => u.length <= 64 && PATTERN.test(u.trim().toLowerCase())
