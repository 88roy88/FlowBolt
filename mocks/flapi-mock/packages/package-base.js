/**
 * @typedef {Object} QuickParamOptions
 * @property {string} name - Parameter name (e.g. 'category')
 * @property {string} [displayName] - Display name (defaults to capitalized name)
 * @property {'String'|'Integer'|'Date'|'Boolean'} [type='String'] - Parameter type
 * @property {string[]} values - Available values (e.g. ['Audio', 'Video'])
 * @property {boolean} [required=false] - Whether this parameter is required
 * @property {boolean} [requireAny=false] - Whether at least one value is required
 * @property {boolean} [singleValue=false] - Whether only one value can be selected
 * @property {boolean} [dynamic=false] - Whether values are dynamically loaded
 * @property {string} [description=''] - Parameter description
 */

/**
 * Build a FLAPI quick parameter definition from simple options.
 * Turns 15+ lines of boilerplate into a single call.
 *
 * @param {QuickParamOptions} opts
 * @param {number} index - 1-based parameter index within the query
 * @param {string} queryId - Query UUID
 * @param {string} queryDisplayName - Query display name
 * @returns {Object} Full FLAPI quick parameter object
 */
export function quickParam(opts, index, queryId, queryDisplayName) {
  const name = opts.name;
  const displayName = opts.displayName || name.charAt(0).toUpperCase() + name.slice(1);
  const type = opts.type || 'String';
  const required = opts.required || false;
  const requireAny = opts.requireAny || false;

  let requiredLabel = 'Optional';
  let tooltip = '';
  if (required) {
    requiredLabel = 'Required';
    tooltip = 'This parameter is required';
  } else if (requireAny) {
    requiredLabel = 'Require Any';
    tooltip = 'At least one value is required';
  }

  const ontology = type === 'Integer' ? 'NUMBER' : type === 'Date' ? 'DATE' : 'TEXT';

  return {
    Name: name,
    ColumnName: `${name}_col`,
    Type: type,
    DisplayName: displayName,
    IsSingleValue: opts.singleValue || false,
    IsRequired: required,
    Visible: true,
    Value: opts.values.map((v) => ({ Name: String(v), Value: String(v) })),
    IsDynamic: opts.dynamic || false,
    IsExcel: type !== 'Integer',
    OntologyType: ontology,
    Attributes: [],
    id: `Input_${name}`,
    data: {},
    quickParameterInfo: {
      DisplayName: displayName,
      Description: opts.description || '',
      RequiredType: {
        IsRequired: required,
        IsRequireAny: requireAny,
        DisplayName: requiredLabel,
        disabledToolTipText: tooltip,
      },
    },
    parameterIndex: index,
    QueryId: queryId,
    QueryDisplayName: queryDisplayName,
  };
}

/**
 * Build a quick params query group.
 * @param {string} queryId
 * @param {string} queryDisplayName
 * @param {QuickParamOptions[]} params
 * @returns {{ [queryId: string]: Object[] }}
 */
export function quickParamsQuery(queryId, queryDisplayName, params) {
  return {
    [queryId]: params.map((p, i) => quickParam(p, i + 1, queryId, queryDisplayName)),
  };
}

/**
 * Shorthand for creating a tag object.
 * @param {string} value
 * @returns {{ value: string, label: string }}
 */
export function tag(value) {
  return { value, label: value };
}

/**
 * @typedef {Object} MockPackageConfig
 * @property {number} id - Unique package ID
 * @property {string} name - Display name
 * @property {{ value: string, label: string }[]} [tags=[]] - Package tags
 * @property {string} [description=''] - Package description
 * @property {Object} [data] - Static data (cubes/tables). Mutually exclusive with getResults.
 * @property {Function} [getResults] - Custom results function. Receives (body, extractQuickParams).
 * @property {{ [cubeOrTable: string]: string[] }} [schema] - Return schema. Auto-derived from data if omitted.
 * @property {Object} [quickParams={}] - Quick parameters info keyed by query ID
 */

/**
 * A mock FLAPI package.
 * Validates required fields and provides sensible defaults.
 */
export class MockPackage {
  /**
   * @param {MockPackageConfig} config
   */
  constructor(config) {
    if (typeof config.id !== 'number') {
      throw new Error(`MockPackage: id must be a number, got ${typeof config.id}`);
    }
    if (typeof config.name !== 'string' || !config.name.trim()) {
      throw new Error(`MockPackage: name is required (id=${config.id})`);
    }
    if (!config.data && !config.getResults) {
      throw new Error(`MockPackage: either data or getResults is required (id=${config.id})`);
    }

    /** @type {number} */
    this.id = config.id;
    /** @type {string} */
    this.name = config.name;
    /** @type {{ value: string, label: string }[]} */
    this.tags = config.tags || [];
    /** @type {string} */
    this.description = config.description || '';
    /** @type {Object} */
    this.quickParams = config.quickParams || {};

    this._data = config.data || null;
    this._getResultsFn = config.getResults || null;

    // Auto-derive schema from data keys if not explicitly provided
    if (config.schema) {
      /** @type {{ [cubeOrTable: string]: string[] }} */
      this.schema = config.schema;
    } else if (this._data) {
      this.schema = MockPackage.deriveSchema(this._data);
    } else {
      this.schema = {};
    }
  }

  /**
   * Derive schema (field names per cube/table) from data object.
   * @param {Object} data
   * @returns {{ [key: string]: string[] }}
   */
  static deriveSchema(data) {
    const schema = {};
    for (const [key, value] of Object.entries(data)) {
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
        schema[key] = Object.keys(value[0]);
      } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        schema[key] = Object.keys(value);
      }
    }
    return schema;
  }

  /**
   * Get results for this package.
   * @param {Object} body - Request body (may contain quick params)
   * @param {Function} extractQuickParams - Helper to extract quick params from body
   * @returns {Object}
   */
  getResults(body, extractQuickParams) {
    if (this._getResultsFn) {
      return this._getResultsFn(body, extractQuickParams);
    }
    return { ...this._data };
  }
}
