/**
 * Autogenerated by Thrift
 *
 * DO NOT EDIT UNLESS YOU ARE SURE THAT YOU KNOW WHAT YOU ARE DOING
 */
package org.apache.hadoop.thriftfs.jobtracker.api;

import java.util.List;
import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.EnumMap;
import java.util.Set;
import java.util.HashSet;
import java.util.EnumSet;
import java.util.Collections;
import java.util.BitSet;
import java.nio.ByteBuffer;
import java.util.Arrays;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.apache.thrift.*;
import org.apache.thrift.async.*;
import org.apache.thrift.meta_data.*;
import org.apache.thrift.transport.*;
import org.apache.thrift.protocol.*;

/**
 * Unique task attempt id
 */
public class ThriftTaskAttemptID implements TBase<ThriftTaskAttemptID, ThriftTaskAttemptID._Fields>, java.io.Serializable, Cloneable {
  private static final TStruct STRUCT_DESC = new TStruct("ThriftTaskAttemptID");

  private static final TField TASK_ID_FIELD_DESC = new TField("taskID", TType.STRUCT, (short)1);
  private static final TField ATTEMPT_ID_FIELD_DESC = new TField("attemptID", TType.I32, (short)2);
  private static final TField AS_STRING_FIELD_DESC = new TField("asString", TType.STRING, (short)3);

  public ThriftTaskID taskID;
  public int attemptID;
  public String asString;

  /** The set of fields this struct contains, along with convenience methods for finding and manipulating them. */
  public enum _Fields implements TFieldIdEnum {
    TASK_ID((short)1, "taskID"),
    ATTEMPT_ID((short)2, "attemptID"),
    AS_STRING((short)3, "asString");

    private static final Map<String, _Fields> byName = new HashMap<String, _Fields>();

    static {
      for (_Fields field : EnumSet.allOf(_Fields.class)) {
        byName.put(field.getFieldName(), field);
      }
    }

    /**
     * Find the _Fields constant that matches fieldId, or null if its not found.
     */
    public static _Fields findByThriftId(int fieldId) {
      switch(fieldId) {
        case 1: // TASK_ID
          return TASK_ID;
        case 2: // ATTEMPT_ID
          return ATTEMPT_ID;
        case 3: // AS_STRING
          return AS_STRING;
        default:
          return null;
      }
    }

    /**
     * Find the _Fields constant that matches fieldId, throwing an exception
     * if it is not found.
     */
    public static _Fields findByThriftIdOrThrow(int fieldId) {
      _Fields fields = findByThriftId(fieldId);
      if (fields == null) throw new IllegalArgumentException("Field " + fieldId + " doesn't exist!");
      return fields;
    }

    /**
     * Find the _Fields constant that matches name, or null if its not found.
     */
    public static _Fields findByName(String name) {
      return byName.get(name);
    }

    private final short _thriftId;
    private final String _fieldName;

    _Fields(short thriftId, String fieldName) {
      _thriftId = thriftId;
      _fieldName = fieldName;
    }

    public short getThriftFieldId() {
      return _thriftId;
    }

    public String getFieldName() {
      return _fieldName;
    }
  }

  // isset id assignments
  private static final int __ATTEMPTID_ISSET_ID = 0;
  private BitSet __isset_bit_vector = new BitSet(1);

  public static final Map<_Fields, FieldMetaData> metaDataMap;
  static {
    Map<_Fields, FieldMetaData> tmpMap = new EnumMap<_Fields, FieldMetaData>(_Fields.class);
    tmpMap.put(_Fields.TASK_ID, new FieldMetaData("taskID", TFieldRequirementType.DEFAULT, 
        new StructMetaData(TType.STRUCT, ThriftTaskID.class)));
    tmpMap.put(_Fields.ATTEMPT_ID, new FieldMetaData("attemptID", TFieldRequirementType.DEFAULT, 
        new FieldValueMetaData(TType.I32)));
    tmpMap.put(_Fields.AS_STRING, new FieldMetaData("asString", TFieldRequirementType.DEFAULT, 
        new FieldValueMetaData(TType.STRING)));
    metaDataMap = Collections.unmodifiableMap(tmpMap);
    FieldMetaData.addStructMetaDataMap(ThriftTaskAttemptID.class, metaDataMap);
  }

  public ThriftTaskAttemptID() {
  }

  public ThriftTaskAttemptID(
    ThriftTaskID taskID,
    int attemptID,
    String asString)
  {
    this();
    this.taskID = taskID;
    this.attemptID = attemptID;
    setAttemptIDIsSet(true);
    this.asString = asString;
  }

  /**
   * Performs a deep copy on <i>other</i>.
   */
  public ThriftTaskAttemptID(ThriftTaskAttemptID other) {
    __isset_bit_vector.clear();
    __isset_bit_vector.or(other.__isset_bit_vector);
    if (other.isSetTaskID()) {
      this.taskID = new ThriftTaskID(other.taskID);
    }
    this.attemptID = other.attemptID;
    if (other.isSetAsString()) {
      this.asString = other.asString;
    }
  }

  public ThriftTaskAttemptID deepCopy() {
    return new ThriftTaskAttemptID(this);
  }

  @Override
  public void clear() {
    this.taskID = null;
    setAttemptIDIsSet(false);
    this.attemptID = 0;
    this.asString = null;
  }

  public ThriftTaskID getTaskID() {
    return this.taskID;
  }

  public ThriftTaskAttemptID setTaskID(ThriftTaskID taskID) {
    this.taskID = taskID;
    return this;
  }

  public void unsetTaskID() {
    this.taskID = null;
  }

  /** Returns true if field taskID is set (has been asigned a value) and false otherwise */
  public boolean isSetTaskID() {
    return this.taskID != null;
  }

  public void setTaskIDIsSet(boolean value) {
    if (!value) {
      this.taskID = null;
    }
  }

  public int getAttemptID() {
    return this.attemptID;
  }

  public ThriftTaskAttemptID setAttemptID(int attemptID) {
    this.attemptID = attemptID;
    setAttemptIDIsSet(true);
    return this;
  }

  public void unsetAttemptID() {
    __isset_bit_vector.clear(__ATTEMPTID_ISSET_ID);
  }

  /** Returns true if field attemptID is set (has been asigned a value) and false otherwise */
  public boolean isSetAttemptID() {
    return __isset_bit_vector.get(__ATTEMPTID_ISSET_ID);
  }

  public void setAttemptIDIsSet(boolean value) {
    __isset_bit_vector.set(__ATTEMPTID_ISSET_ID, value);
  }

  public String getAsString() {
    return this.asString;
  }

  public ThriftTaskAttemptID setAsString(String asString) {
    this.asString = asString;
    return this;
  }

  public void unsetAsString() {
    this.asString = null;
  }

  /** Returns true if field asString is set (has been asigned a value) and false otherwise */
  public boolean isSetAsString() {
    return this.asString != null;
  }

  public void setAsStringIsSet(boolean value) {
    if (!value) {
      this.asString = null;
    }
  }

  public void setFieldValue(_Fields field, Object value) {
    switch (field) {
    case TASK_ID:
      if (value == null) {
        unsetTaskID();
      } else {
        setTaskID((ThriftTaskID)value);
      }
      break;

    case ATTEMPT_ID:
      if (value == null) {
        unsetAttemptID();
      } else {
        setAttemptID((Integer)value);
      }
      break;

    case AS_STRING:
      if (value == null) {
        unsetAsString();
      } else {
        setAsString((String)value);
      }
      break;

    }
  }

  public Object getFieldValue(_Fields field) {
    switch (field) {
    case TASK_ID:
      return getTaskID();

    case ATTEMPT_ID:
      return new Integer(getAttemptID());

    case AS_STRING:
      return getAsString();

    }
    throw new IllegalStateException();
  }

  /** Returns true if field corresponding to fieldID is set (has been asigned a value) and false otherwise */
  public boolean isSet(_Fields field) {
    if (field == null) {
      throw new IllegalArgumentException();
    }

    switch (field) {
    case TASK_ID:
      return isSetTaskID();
    case ATTEMPT_ID:
      return isSetAttemptID();
    case AS_STRING:
      return isSetAsString();
    }
    throw new IllegalStateException();
  }

  @Override
  public boolean equals(Object that) {
    if (that == null)
      return false;
    if (that instanceof ThriftTaskAttemptID)
      return this.equals((ThriftTaskAttemptID)that);
    return false;
  }

  public boolean equals(ThriftTaskAttemptID that) {
    if (that == null)
      return false;

    boolean this_present_taskID = true && this.isSetTaskID();
    boolean that_present_taskID = true && that.isSetTaskID();
    if (this_present_taskID || that_present_taskID) {
      if (!(this_present_taskID && that_present_taskID))
        return false;
      if (!this.taskID.equals(that.taskID))
        return false;
    }

    boolean this_present_attemptID = true;
    boolean that_present_attemptID = true;
    if (this_present_attemptID || that_present_attemptID) {
      if (!(this_present_attemptID && that_present_attemptID))
        return false;
      if (this.attemptID != that.attemptID)
        return false;
    }

    boolean this_present_asString = true && this.isSetAsString();
    boolean that_present_asString = true && that.isSetAsString();
    if (this_present_asString || that_present_asString) {
      if (!(this_present_asString && that_present_asString))
        return false;
      if (!this.asString.equals(that.asString))
        return false;
    }

    return true;
  }

  @Override
  public int hashCode() {
    return 0;
  }

  public int compareTo(ThriftTaskAttemptID other) {
    if (!getClass().equals(other.getClass())) {
      return getClass().getName().compareTo(other.getClass().getName());
    }

    int lastComparison = 0;
    ThriftTaskAttemptID typedOther = (ThriftTaskAttemptID)other;

    lastComparison = Boolean.valueOf(isSetTaskID()).compareTo(typedOther.isSetTaskID());
    if (lastComparison != 0) {
      return lastComparison;
    }
    if (isSetTaskID()) {
      lastComparison = TBaseHelper.compareTo(this.taskID, typedOther.taskID);
      if (lastComparison != 0) {
        return lastComparison;
      }
    }
    lastComparison = Boolean.valueOf(isSetAttemptID()).compareTo(typedOther.isSetAttemptID());
    if (lastComparison != 0) {
      return lastComparison;
    }
    if (isSetAttemptID()) {
      lastComparison = TBaseHelper.compareTo(this.attemptID, typedOther.attemptID);
      if (lastComparison != 0) {
        return lastComparison;
      }
    }
    lastComparison = Boolean.valueOf(isSetAsString()).compareTo(typedOther.isSetAsString());
    if (lastComparison != 0) {
      return lastComparison;
    }
    if (isSetAsString()) {
      lastComparison = TBaseHelper.compareTo(this.asString, typedOther.asString);
      if (lastComparison != 0) {
        return lastComparison;
      }
    }
    return 0;
  }

  public _Fields fieldForId(int fieldId) {
    return _Fields.findByThriftId(fieldId);
  }

  public void read(TProtocol iprot) throws TException {
    TField field;
    iprot.readStructBegin();
    while (true)
    {
      field = iprot.readFieldBegin();
      if (field.type == TType.STOP) { 
        break;
      }
      switch (field.id) {
        case 1: // TASK_ID
          if (field.type == TType.STRUCT) {
            this.taskID = new ThriftTaskID();
            this.taskID.read(iprot);
          } else { 
            TProtocolUtil.skip(iprot, field.type);
          }
          break;
        case 2: // ATTEMPT_ID
          if (field.type == TType.I32) {
            this.attemptID = iprot.readI32();
            setAttemptIDIsSet(true);
          } else { 
            TProtocolUtil.skip(iprot, field.type);
          }
          break;
        case 3: // AS_STRING
          if (field.type == TType.STRING) {
            this.asString = iprot.readString();
          } else { 
            TProtocolUtil.skip(iprot, field.type);
          }
          break;
        default:
          TProtocolUtil.skip(iprot, field.type);
      }
      iprot.readFieldEnd();
    }
    iprot.readStructEnd();

    // check for required fields of primitive type, which can't be checked in the validate method
    validate();
  }

  public void write(TProtocol oprot) throws TException {
    validate();

    oprot.writeStructBegin(STRUCT_DESC);
    if (this.taskID != null) {
      oprot.writeFieldBegin(TASK_ID_FIELD_DESC);
      this.taskID.write(oprot);
      oprot.writeFieldEnd();
    }
    oprot.writeFieldBegin(ATTEMPT_ID_FIELD_DESC);
    oprot.writeI32(this.attemptID);
    oprot.writeFieldEnd();
    if (this.asString != null) {
      oprot.writeFieldBegin(AS_STRING_FIELD_DESC);
      oprot.writeString(this.asString);
      oprot.writeFieldEnd();
    }
    oprot.writeFieldStop();
    oprot.writeStructEnd();
  }

  @Override
  public String toString() {
    StringBuilder sb = new StringBuilder("ThriftTaskAttemptID(");
    boolean first = true;

    sb.append("taskID:");
    if (this.taskID == null) {
      sb.append("null");
    } else {
      sb.append(this.taskID);
    }
    first = false;
    if (!first) sb.append(", ");
    sb.append("attemptID:");
    sb.append(this.attemptID);
    first = false;
    if (!first) sb.append(", ");
    sb.append("asString:");
    if (this.asString == null) {
      sb.append("null");
    } else {
      sb.append(this.asString);
    }
    first = false;
    sb.append(")");
    return sb.toString();
  }

  public void validate() throws TException {
    // check for required fields
  }

}

