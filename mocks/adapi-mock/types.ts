/** Shape of a user record served by ADAPI (mirrors an Active Directory user). */
export interface AdUser {
  cn: string;
  displayName: string;
  distinguishedName: string;
  givenName: string;
  ipPhone: string;
  mail: string;
  objectGUID: string;
  objectSid: string;
  sAMAccountName: string;
  sn: string;
  userAccountControl: string;
  extensionAttribute10: string;
}

/** Shape of a group record served by ADAPI (mirrors an Active Directory group). */
export interface AdGroup {
  cn: string;
  displayName: string;
  distinguishedName: string;
  description: string;
  groupType: string;
  mail: string;
  mailNickname: string;
  /** DN of the user that manages this group (references users.json). */
  managedBy: string;
  /** DNs of users that belong to this group (references users.json). */
  member: string[];
  /** DNs of parent groups this group is nested under (references groups.json). */
  memberOf: string[];
  sAMAccountName: string;
  objectGUID: string;
}
